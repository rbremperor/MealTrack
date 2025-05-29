from rest_framework import serializers
from .models import *



class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = '__all__'


class MealIngredientSerializer(serializers.ModelSerializer):
    ingredient = IngredientSerializer()
    possible_portions = serializers.SerializerMethodField()

    class Meta:
        model = MealIngredient
        fields = ['id', 'ingredient', 'quantity', 'possible_portions']

    def get_possible_portions(self, obj):
        return int(obj.ingredient.current_quantity // obj.quantity)


class MealSerializer(serializers.ModelSerializer):
    ingredients = MealIngredientSerializer(source='meal_ingredients', many=True)
    possible_portions = serializers.SerializerMethodField()

    class Meta:
        model = Meal
        fields = ['id', 'name', 'description', 'ingredients', 'possible_portions', 'created_at', 'updated_at']

    def get_possible_portions(self, obj):
        return obj.possible_portions


class MealServingSerializer(serializers.ModelSerializer):
    meal = serializers.StringRelatedField()

    class Meta:
        model = MealServing
        fields = '__all__'


class MealServeSerializer(serializers.Serializer):
    servings = serializers.IntegerField(min_value=1)

    def validate(self, data):
        meal = self.context['meal']
        servings = data['servings']

        insufficient = []
        for mi in meal.meal_ingredients.all():
            required = mi.quantity * servings
            if mi.ingredient.current_quantity < required:
                insufficient.append({
                    'ingredient': mi.ingredient.name,
                    'required': float(required),
                    'available': float(mi.ingredient.current_quantity)
                })

        if insufficient:
            raise serializers.ValidationError({
                'error': 'Insufficient ingredients',
                'details': insufficient
            })

        return data