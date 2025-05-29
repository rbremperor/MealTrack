from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    # Dashboard URL
    path('dashboard/', views.dashboard, name='report_dashboard'),
    path('dashboard/export/csv/', views.export_csv, name='export_csv'),
    path('dashboard/export/pdf/', views.export_pdf, name='export_pdf'),
    # Ingredient URLs
    path('ingredients/', views.ingredient_list, name='ingredient-list'),
    path('ingredients/new/', views.ingredient_form, name='ingredient-create'),
    path('ingredients/<int:pk>/edit/', views.ingredient_form, name='ingredient-edit'),
    path('deliveries/new/', views.create_ingredient_delivery, name='create_ingredient_delivery'),

    # Meal URLs
    path('meals/', views.meal_list, name='meal-list'),
    path('meals/new/', views.meal_form, name='meal-create'),
    path('meals/<int:pk>/edit/', views.meal_form, name='meal-edit'),

    # Serve Meal URL
    path('meals/<int:pk>/serve/', views.serve_meal, name='meal-serve'),

    # API URLs for the ViewSets (optional, if you want REST API routes)
    path('api/ingredients/', views.IngredientViewSet.as_view({'get': 'list'}), name='api-ingredients'),
    path('api/ingredients/<int:pk>/',
         views.IngredientViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}),
         name='api-ingredient-detail'),
    path('api/meals/', views.MealViewSet.as_view({'get': 'list'}), name='api-meals'),
    path('api/meals/<int:pk>/', views.MealViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}),
         name='api-meal-detail'),
    path('api/meal-servings/', views.MealServingViewSet.as_view({'get': 'list'}), name='api-meal-servings'),

]
