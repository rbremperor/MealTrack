from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Ingredient, IngredientDelivery, MealServing
from .tasks import update_dashboard_cache

@receiver(post_save, sender=Ingredient)
def trigger_cache_on_low_stock(sender, instance, **kwargs):
    if instance.is_active and instance.current_quantity < instance.minimum_quantity:
        update_dashboard_cache.delay()

@receiver(post_save, sender=IngredientDelivery)
def trigger_cache_on_delivery(sender, instance, **kwargs):
    update_dashboard_cache.delay()

@receiver(post_save, sender=MealServing)
def trigger_cache_on_serving(sender, instance, **kwargs):
    update_dashboard_cache.delay()
