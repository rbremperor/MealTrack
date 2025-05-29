from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, F, FloatField
from django.utils.dateparse import parse_date
from django.db.models.functions import TruncMonth
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from django.contrib import messages

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from reportlab.pdfgen import canvas
from io import BytesIO
import csv
from collections import OrderedDict
import calendar
from datetime import datetime
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .serializers import *
from .forms import *
from .permissions import *

year = datetime.now().year
all_months = OrderedDict()

# HTML Views
def home(request):
    meals = MealServing.objects.all()
    return render(request, 'home.html', {
        'meals': meals, })

@login_required
@user_passes_test(lambda u: u.role in ('admin', 'manager'))
def dashboard(request):
    try:
        cache = DashboardCache.objects.latest('last_updated')
        data = cache.data
    except DashboardCache.DoesNotExist:
        data = {}

    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    servings_over_time = data.get('servings_over_time', {})
    labels = servings_over_time.get('labels', [])
    servings = servings_over_time.get('values', [])

    top_meals = data.get('top_meals', [])
    top_meal_labels = [meal['name'] for meal in top_meals]
    top_meal_values = [meal['count'] for meal in top_meals]

    monthly_summary = data.get('monthly_summary', [])
    summary_labels = [m['month'] for m in monthly_summary]
    total_served = [m['served'] for m in monthly_summary]
    total_possible = [m['possible'] for m in monthly_summary]
    difference_rate = [m['difference_rate'] for m in monthly_summary]
    flags = [m['flag'] for m in monthly_summary]

    table_log = MealServing.objects.order_by('-served_at')[:10]

    context = {
        'start_date': start_date,
        'end_date': end_date,
        'low_stock_alerts': data.get('low_stock_alerts', []),
        'consumption_data': json.dumps(data.get('consumption_data', [])),
        'consumption_labels': json.dumps(data.get('consumption_labels', [])),
        'delivery_data': json.dumps(data.get('delivery_data', [])),
        'delivery_labels': json.dumps(data.get('delivery_labels', [])),
        'labels': json.dumps(labels),
        'servings': json.dumps(servings),
        'top_meal_labels': json.dumps(top_meal_labels),
        'top_meal_values': json.dumps(top_meal_values),
        'summary_labels': json.dumps(summary_labels),
        'total_served': json.dumps(total_served),
        'total_possible': json.dumps(total_possible),
        'difference_rate': json.dumps(difference_rate),
        'flags': json.dumps(flags),
        'table_log': table_log,
        'cache_exists': bool(data),
    }

    return render(request, 'dashboard.html', context)


@login_required
@user_passes_test(lambda u: u.role in ('admin', 'manager'))
def export_csv(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    meal_servings = MealServing.objects.all()

    if start_date and end_date:
        start = parse_date(start_date)
        end = parse_date(end_date)
        if start and end:
            meal_servings = meal_servings.filter(served_at__date__range=[start, end])

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="meal_servings.csv"'

    writer = csv.writer(response)
    writer.writerow(['Meal', 'Servings', 'Served At'])

    for serving in meal_servings:
        writer.writerow([serving.meal.name, serving.servings, serving.served_at.strftime('%Y-%m-%d %H:%M')])

    return response


@login_required
@user_passes_test(lambda u: u.role in ('admin', 'manager'))
def export_pdf(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    meal_servings = MealServing.objects.all()

    if start_date and end_date:
        start = parse_date(start_date)
        end = parse_date(end_date)
        if start and end:
            meal_servings = meal_servings.filter(served_at__date__range=[start, end])

    buffer = BytesIO()
    p = canvas.Canvas(buffer)
    p.setFont("Helvetica", 12)
    p.drawString(100, 800, "Meal Serving Report")

    y = 780
    for serving in meal_servings:
        line = f"{serving.served_at.strftime('%Y-%m-%d')} | {serving.meal.name} x{serving.servings}"
        p.drawString(50, y, line)
        y -= 20
        if y < 50:
            p.showPage()
            y = 800

    p.showPage()
    p.save()
    buffer.seek(0)

    return HttpResponse(buffer, content_type='application/pdf')


@login_required
@user_passes_test(lambda u: u.role in ('admin', 'manager'))
def ingredient_list(request):
    ingredients = Ingredient.objects.filter(is_active=True)
    return render(request, 'ingredients/list.html', {'ingredients': ingredients})


@login_required
@user_passes_test(lambda u: u.role in ('admin', 'manager'))
def ingredient_form(request, pk=None):
    ingredient = get_object_or_404(Ingredient.objects.filter(is_active=True), pk=pk) if pk else None

    if request.method == 'POST':
        form = IngredientForm(request.POST, instance=ingredient)
        if form.is_valid():
            form.save()
            return redirect('ingredient-list')
    else:
        form = IngredientForm(instance=ingredient)

    context = {
        'form': form,
        'ingredient': ingredient,
        'is_edit': bool(pk),
    }
    return render(request, 'ingredients/form.html', context)


@login_required
def create_ingredient_delivery(request):
    if request.method == 'POST':
        form = IngredientDeliveryForm(request.POST)
        if form.is_valid():
            delivery = form.save(commit=False)
            delivery.delivered_by = request.user
            delivery.save()

            # Update the ingredient stock
            ingredient = delivery.ingredient
            ingredient.current_quantity += delivery.quantity
            ingredient.delivery_date = delivery.delivered_at
            ingredient.save()

            return redirect('/ingredients/')  # or wherever appropriate
    else:
        form = IngredientDeliveryForm()

    return render(request, 'ingredients/delivery.html', {'form': form})


@login_required
@user_passes_test(lambda u: u.role in ('admin', 'manager', 'cook'))
def meal_list(request):
    meals = Meal.objects.filter(is_active=True).prefetch_related('meal_ingredients')
    return render(request, 'meals/list.html', {'meals': meals})


@login_required
@user_passes_test(lambda u: u.role in ('admin', 'manager'))
def meal_form(request, pk=None):
    meal = get_object_or_404(Meal, pk=pk) if pk else None
    if request.user.groups.filter(name='Cook').exists():
        messages.warning(request, "Warning: You have limited permissions to add meals!")
    if request.method == 'POST':
        form = MealForm(request.POST, instance=meal)
        formset = MealIngredientFormSet(request.POST, instance=meal)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                meal = form.save()
                formset.instance = meal
                formset.save()
            return redirect('meal-list')
    else:
        form = MealForm(instance=meal)
        formset = MealIngredientFormSet(instance=meal)

    return render(request, 'meals/form.html', {
        'form': form,
        'formset': formset,
        'meal': meal,
    })


def notify_inventory_update(ingredient):
    low_stock = Ingredient.objects.filter(
        current_quantity__lt=F('minimum_quantity'),
        is_active=True
    )
    alerts = [{
        'name': ing.name,
        'quantity': float(ing.current_quantity),
        'unit': ing.unit,
        'minimum': float(ing.minimum_quantity)
    } for ing in low_stock]

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "inventory_updates",
        {
            "type": "send_inventory_update",
            "data": {
                "type": "low_stock_alerts",
                "alerts": alerts
            }
        }
    )

@login_required
@user_passes_test(lambda u: u.role in ('admin', 'manager', 'cook'))
def serve_meal(request, pk):
    meal = get_object_or_404(Meal, pk=pk)
    if request.method == 'POST':
        form = MealServeForm(request.POST, meal=meal)
        if form.is_valid():
            servings = form.cleaned_data['servings']
            for mi in meal.meal_ingredients.all():
                required_qty = mi.quantity * servings
                if mi.ingredient.current_quantity < required_qty:
                    form.add_error(None, f"Not enough {mi.ingredient.name} in stock.")
                    return render(request, 'meals/serve.html', {
                        'meal': meal,
                        'form': form,
                        'possible_portions': meal.possible_portions
                    })

            with transaction.atomic():
                for mi in meal.meal_ingredients.all():
                    mi.ingredient.current_quantity -= mi.quantity * servings
                    mi.ingredient.save()

                    # ✅ Notify WebSocket clients of updated inventory
                    notify_inventory_update(mi.ingredient)

                possible_portions = meal.possible_portions

                MealServing.objects.create(
                    meal=meal,
                    servings=servings,
                    served_by=request.user,
                    possible_portions_at_serving=possible_portions
                )

            return redirect('meal-list')
    else:
        form = MealServeForm(meal=meal)

    return render(request, 'meals/serve.html', {
        'meal': meal,
        'form': form,
        'possible_portions': meal.possible_portions
    })


# API Views

class IngredientViewSet(viewsets.ModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = [IsAuthenticated, IsManager, IsAdmin]

    @action(detail=True, methods=['post'])
    def deliver(self, request, pk=None):
        ingredient = self.get_object()
        serializer = IngredientSerializer(ingredient, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(delivery_date=timezone.now().date())
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response({'detail': 'Ingredient marked as inactive.'}, status=status.HTTP_204_NO_CONTENT)


class MealViewSet(viewsets.ModelViewSet):
    queryset = Meal.objects.all()
    serializer_class = MealSerializer

    def get_permissions(self):
        if self.action == 'serve':
            return [IsAuthenticated(), IsCook()]
        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdmin()]
        return [IsAuthenticated()]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response({'detail': 'Ingredient marked as inactive.'}, status=status.HTTP_204_NO_CONTENT)


class MealServingViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = MealServingSerializer
    permission_classes = [IsAuthenticated, IsManagerOrAdmin]

    def get_queryset(self):
        queryset = MealServing.objects.all()
        if self.request.query_params.get('meal'):
            queryset = queryset.filter(meal=self.request.query_params.get('meal'))
        return queryset.order_by('-served_at')
