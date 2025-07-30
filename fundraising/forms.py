from django import forms
from .models import Campaign, Donation

class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ['title', 'description', 'goal', 'image']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full border border-gray-300 rounded-md p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'e.g., Help Me Complete My Computer Science Degree'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full border border-gray-300 rounded-md p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'rows': 6,
                'placeholder': 'Tell your story... Why do you need funding? What are your educational goals? How will this help your future?'
            }),
            'goal': forms.NumberInput(attrs={
                'class': 'w-full border border-gray-300 rounded-md p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'min': '1',
                'step': '0.01',
                'placeholder': '5000.00'
            }),
            'image': forms.FileInput(attrs={
                'class': 'w-full border border-gray-300 rounded-md p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'accept': 'image/*'
            }),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].help_text = "Choose a clear, compelling title that describes your educational goal"
        self.fields['description'].help_text = "Share your story, explain your goals, and tell donors how their support will make a difference"
        self.fields['goal'].help_text = "Set a realistic amount based on your actual educational expenses"
        self.fields['image'].help_text = "Upload a photo of yourself or something that represents your educational journey"
        
    def clean_goal(self):
        goal = self.cleaned_data.get('goal')
        if goal and goal < 1:
            raise forms.ValidationError("Goal amount must be at least $1")
        if goal and goal > 100000:
            raise forms.ValidationError("Goal amount cannot exceed $100,000")
        return goal
        
    def clean_title(self):
        title = self.cleaned_data.get('title')
        if title and len(title) < 10:
            raise forms.ValidationError("Title must be at least 10 characters long")
        return title
        
    def clean_description(self):
        description = self.cleaned_data.get('description')
        if description and len(description) < 50:
            raise forms.ValidationError("Description must be at least 50 characters long")
        return description

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
