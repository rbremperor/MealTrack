# app/tasks.py

from celery import shared_task
from django.db.models import Sum, F, FloatField
from django.db.models.functions import TruncDay
from .models import DashboardCache, MealServing, IngredientDelivery, Ingredient
from datetime import datetime

# WebSocket related imports
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


@shared_task
def update_dashboard_cache():
    # ------------------ INGREDIENT CONSUMPTION OVER TIME (Daily) ------------------
    servings = MealServing.objects.all()
    consumption_qs = (
        servings
        .annotate(day=TruncDay('served_at'))
        .values('day', 'meal__meal_ingredients__ingredient__name')
        .annotate(
            consumed_qty=Sum(
                F('meal__meal_ingredients__quantity') * F('servings'),
                output_field=FloatField()
            )
        )
        .order_by('day')
    )

    consumption_dict = {}
    consumption_labels = set()

    for item in consumption_qs:
        ing = item['meal__meal_ingredients__ingredient__name']
        day = item['day'].strftime('%Y-%m-%d')
        qty = float(item['consumed_qty']) if item['consumed_qty'] else 0.0
        consumption_labels.add(day)

        if ing not in consumption_dict:
            consumption_dict[ing] = []
        consumption_dict[ing].append({'day': day, 'qty': qty})

    consumption_data = [{'ingredient': ing, 'data': data} for ing, data in consumption_dict.items()]

    # ------------------ INGREDIENT DELIVERY OVER TIME (Daily) ------------------
    delivery_qs = (
        IngredientDelivery.objects
        .annotate(day=TruncDay('delivered_at'))
        .values('day', 'ingredient__name')
        .annotate(delivered_qty=Sum('quantity'))
        .order_by('day')
    )

    delivery_dict = {}
    delivery_labels = set()

    for item in delivery_qs:
        ing = item['ingredient__name']
        day = item['day'].strftime('%Y-%m-%d')
        qty = float(item['delivered_qty']) if item['delivered_qty'] else 0.0
        delivery_labels.add(day)

        if ing not in delivery_dict:
            delivery_dict[ing] = []
        delivery_dict[ing].append({'day': day, 'qty': qty})

    delivery_data = [{'ingredient': ing, 'data': data} for ing, data in delivery_dict.items()]

    # ------------------ LOW STOCK ALERTS ------------------
    low_stock_ingredients = Ingredient.objects.filter(
        current_quantity__lt=F('minimum_quantity'),
        is_active=True
    )

    low_stock_alerts = [
        {
            'name': ing.name,
            'quantity': float(ing.current_quantity),
            'unit': ing.unit,
            'minimum': float(ing.minimum_quantity)
        }
        for ing in low_stock_ingredients
    ]

    # ------------------ DAILY SUMMARY ------------------
    summary_qs = (
        servings
        .annotate(day=TruncDay('served_at'))
        .values('day')
        .annotate(
            total_served=Sum('servings'),
            total_possible=Sum('possible_portions_at_serving')
        )
        .order_by('day')
    )

    daily_summary = []
    for item in summary_qs:
        served = item['total_served'] or 0
        possible = item['total_possible'] or 0
        rate = round((served / possible) * 100, 2) if possible > 0 else 0
        flag = rate < 80  # example flag logic
        daily_summary.append({
            'day': item['day'].strftime('%Y-%m-%d'),
            'served': served,
            'possible': possible,
            'difference_rate': rate,
            'flag': flag,
        })

    # ------------------ TOP MEALS ------------------
    top_meals_qs = (
        servings
        .values('meal__name')
        .annotate(total=Sum('servings'))
        .order_by('-total')[:5]
    )

    top_meals_data = [
        {'name': m['meal__name'], 'count': m['total']}
        for m in top_meals_qs
    ]

    # ------------------ SERVINGS OVER TIME (Daily) ------------------
    servings_over_time_qs = (
        servings
        .annotate(day=TruncDay('served_at'))
        .values('day')
        .annotate(total=Sum('servings'))
        .order_by('day')
    )

    servings_over_time = {
        'labels': [item['day'].strftime('%Y-%m-%d') for item in servings_over_time_qs],
        'values': [item['total'] for item in servings_over_time_qs],
    }

    # ------------------ SAVE TO CACHE ------------------
    cache_data = {
        'consumption_data': consumption_data,
        'consumption_labels': sorted(consumption_labels),
        'delivery_data': delivery_data,
        'delivery_labels': sorted(delivery_labels),
        'low_stock_alerts': low_stock_alerts,
        'daily_summary': daily_summary,
        'top_meals': top_meals_data,
        'servings_over_time': servings_over_time,
    }

    DashboardCache.objects.update_or_create(id=1, defaults={'data': cache_data})

    # ------------------ SEND LOW STOCK ALERTS VIA WEBSOCKET ------------------
    if low_stock_alerts:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "inventory_updates",
            {
                "type": "send_inventory_update",
                "data": {
                    "type": "low_stock_alerts",
                    "alerts": low_stock_alerts,
                },
            }
        )
