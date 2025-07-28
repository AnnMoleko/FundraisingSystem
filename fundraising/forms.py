from django import forms
from .models import Campaign, Donation

class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ['title', 'description', 'goal', 'image']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-blue-500 focus:border-blue-500'}),
            'description': forms.Textarea(attrs={'class': 'w-full border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-blue-500 focus:border-blue-500', 'rows': 5}),
            'goal': forms.NumberInput(attrs={'class': 'w-full border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-blue-500 focus:border-blue-500', 'min': '1', 'step': '0.01'}),
            'image': forms.FileInput(attrs={'class': 'w-full border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-blue-500 focus:border-blue-500'}),
        }

class DonationForm(forms.ModelForm):
    payment_method = forms.ChoiceField(
        choices=[
            ('paypal', 'PayPal'),
            ('mobile_money', 'Mobile Money'),
            ('bank_transfer', 'Bank Transfer'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'mr-2'})
    )
    
    class Meta:
        model = Donation
        fields = ['amount', 'payment_method', 'anonymous']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'w-full border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-blue-500 focus:border-blue-500', 'min': '1', 'step': '0.01'}),
            'anonymous': forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'}),
        }
