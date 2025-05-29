from django import forms
from .models import *
import json

class IngredientForm(forms.ModelForm):
    class Meta:
        model = Ingredient
        fields = ['name', 'unit', 'minimum_quantity', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
            'current_quantity': forms.NumberInput(attrs={'step': '0.001'}),
            'minimum_quantity': forms.NumberInput(attrs={'step': '0.001'}),
            'unit': forms.Select(choices=Ingredient.UNITS),
        }

    def clean(self):
        cleaned_data = super().clean()
        current_quantity = cleaned_data.get('current_quantity')
        minimum_quantity = cleaned_data.get('minimum_quantity')
        if current_quantity is not None and current_quantity < 0:
            raise forms.ValidationError({"current_quantity": "Current quantity cannot be negative."})
        if minimum_quantity is not None and minimum_quantity < 0:
            raise forms.ValidationError({"minimum_quantity": "Minimum quantity cannot be negative."})
        return cleaned_data

class MealForm(forms.ModelForm):
    class Meta:
        model = Meal
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }

class MealIngredientForm(forms.ModelForm):
    class Meta:
        model = MealIngredient
        fields = ['ingredient', 'quantity']
        widgets = {
            'quantity': forms.NumberInput(attrs={'step': '0.001', 'class': 'form-control'}),
            'ingredient': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ingredients = Ingredient.objects.order_by('name')
        self.fields['ingredient'].queryset = ingredients
        self.fields['ingredient'].widget.attrs['data-units'] = json.dumps({
            str(i.pk): i.unit for i in ingredients
        })

MealIngredientFormSet = forms.inlineformset_factory(
    Meal,
    MealIngredient,
    form=MealIngredientForm,
    extra=1,
    can_delete=True
)

class MealServeForm(forms.ModelForm):
    class Meta:
        model = MealServing
        fields = ['servings', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        self.meal = kwargs.pop('meal', None)
        super().__init__(*args, **kwargs)
        if self.meal:
            self.fields['servings'].widget.attrs['max'] = self.meal.possible_portions


class IngredientDeliveryForm(forms.ModelForm):
    class Meta:
        model = IngredientDelivery
        fields = ['ingredient', 'quantity', 'delivered_by']
        widgets = {
            'delivered_by': forms.HiddenInput()
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ingredient'].queryset = self.fields['ingredient'].queryset.filter(is_active=True)

        # Add Bootstrap class to visible fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ != forms.HiddenInput:
                field.widget.attrs.update({'class': 'form-control'})
