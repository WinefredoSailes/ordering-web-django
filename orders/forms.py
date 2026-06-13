from django import forms
from django.core.exceptions import ValidationError
from .models import Order, Truck, Compartment, Product


class OrderCreateForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['product', 'quantity_liters', 'delivery_address', 'notes']
        widgets = {
            'delivery_address': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Delivery address...'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Additional notes...'}),
        }

    def clean_quantity_liters(self):
        quantity = self.cleaned_data['quantity_liters']
        if quantity % 500 != 0:
            raise ValidationError('Quantity must be a multiple of 500 liters.')
        if quantity <= 0:
            raise ValidationError('Quantity must be greater than 0.')
        return quantity


class PaymentProofForm(forms.Form):
    payment_proof = forms.ImageField(
        label='Payment Proof',
        help_text='Upload a photo of your payment receipt'
    )


class TruckForm(forms.ModelForm):
    class Meta:
        model = Truck
        fields = ['truck_number', 'plate_number', 'total_capacity_liters', 'compartments_count', 'is_active']
        widgets = {
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CompartmentForm(forms.ModelForm):
    class Meta:
        model = Compartment
        fields = ['compartment_number', 'capacity_liters']


class DispatchForm(forms.Form):
    truck = forms.ModelChoiceField(queryset=Truck.objects.filter(is_active=True))
    compartment = forms.ModelChoiceField(queryset=Compartment.objects.none())
    driver = forms.ModelChoiceField(
        queryset=Product.objects.none(),
        label='Driver'
    )