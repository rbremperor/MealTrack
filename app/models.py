from django.db import models
from django.db.models import Q
from django.conf import settings
from django.contrib.auth.models import AbstractUser, Permission, Group
from django.core.validators import MinValueValidator

class DashboardCache(models.Model):
    data = models.JSONField()
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"DashboardCache updated at {self.last_updated}"

class Ingredient(models.Model):
    UNITS = (
        ('g', 'Grams'),
        ('kg', 'Kilograms'),
        ('ml', 'Milliliters'),
        ('l', 'Liters'),
        ('pcs', 'Pieces'),
    )

    name = models.CharField(max_length=100, unique=True)
    current_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(0)],
        default=0
    )
    unit = models.CharField(max_length=3, choices=UNITS, default='g')
    minimum_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(0)]
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ingredients_accepted'
    )
    def __str__(self):
        return f"{self.name} ({self.current_quantity}{self.unit})"

    class Meta:
        ordering = ['name']

class IngredientDelivery(models.Model):
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, related_name='deliveries')
    quantity = models.DecimalField(max_digits=10, decimal_places=3, validators=[MinValueValidator(0)])
    delivered_at = models.DateField(auto_now_add=True)
    delivered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ingredient_deliveries'
    )

    def __str__(self):
        return f"{self.quantity}{self.ingredient.unit} of {self.ingredient.name} on {self.delivered_at}"


class Meal(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['name'],
                condition=Q(is_active=True),
                name='unique_active_meal_name'
            )
        ]

    def __str__(self):
        return self.name

    @property
    def possible_portions(self):
        min_portions = None
        for ingredient in self.meal_ingredients.all():
            portions = ingredient.ingredient.current_quantity // ingredient.quantity
            if min_portions is None or portions < min_portions:
                min_portions = portions
        return int(min_portions) if min_portions else 0

class MealIngredient(models.Model):
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name='meal_ingredients')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT)
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(0.001)]
    )

    class Meta:
        unique_together = ('meal', 'ingredient')
        ordering = ['ingredient__name']

    def __str__(self):
        return f"{self.quantity}{self.ingredient.unit} {self.ingredient.name} in {self.meal.name}"


class MealServing(models.Model):
    meal = models.ForeignKey(Meal, on_delete=models.PROTECT)
    servings = models.PositiveIntegerField(default=1)
    served_at = models.DateTimeField(auto_now_add=True)
    served_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='meal_servings'
    )
    notes = models.TextField(blank=True)
    possible_portions_at_serving = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-served_at']

    def __str__(self):
        return f"{self.meal} x{self.servings} at {self.served_at}"

