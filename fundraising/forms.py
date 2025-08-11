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
    # Predefined donation amounts for quick selection
    QUICK_AMOUNTS = [
        (25, '$25'),
        (50, '$50'),
        (100, '$100'),
        (250, '$250'),
        (500, '$500'),
    ]
    
    # Enhanced payment method choices with descriptions
    PAYMENT_METHODS = [
        ('paypal', 'PayPal - Secure online payment'),
        ('stripe', 'Credit/Debit Card - Visa, MasterCard, etc.'),
        ('mobile_money', 'Mobile Money - M-Pesa, Airtel Money, etc.'),
        ('bank_transfer', 'Bank Transfer - Direct bank transfer'),
        ('crypto', 'Cryptocurrency - Bitcoin, Ethereum'),
    ]
    
    # Custom amount field with better validation
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'w-full border border-gray-300 rounded-md p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-lg',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '1'
        }),
        help_text="Minimum donation amount is $1"
    )
    
    # Payment method with radio buttons
    payment_method = forms.ChoiceField(
        choices=PAYMENT_METHODS,
        widget=forms.RadioSelect(attrs={
            'class': 'payment-method-radio'
        }),
        help_text="Choose your preferred payment method"
    )
    
    # Optional donor message
    message = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full border border-gray-300 rounded-md p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            'rows': 3,
            'placeholder': 'Leave an encouraging message for the student (optional)'
        }),
        help_text="Share words of encouragement or support (optional)"
    )
    
    # Recurring donation option
    is_recurring = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
        }),
        help_text="Make this a monthly recurring donation"
    )
    
    # Cover processing fees option
    cover_fees = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
        }),
        help_text="Add a small amount to cover processing fees (recommended)"
    )
    
    class Meta:
        model = Donation
        fields = ['amount', 'payment_method', 'message', 'anonymous', 'is_recurring', 'cover_fees']
        widgets = {
            'anonymous': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.campaign = kwargs.pop('campaign', None)
        super().__init__(*args, **kwargs)
        
        # Add campaign-specific validation if needed
        if self.campaign:
            remaining_amount = self.campaign.goal - self.campaign.current_amount
            if remaining_amount > 0:
                self.fields['amount'].help_text = f"Minimum: $1 | Remaining to goal: ${remaining_amount:,.2f}"
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        
        if amount < 1:
            raise forms.ValidationError("Minimum donation amount is $1")
        
        if amount > 10000:
            raise forms.ValidationError("Maximum single donation is $10,000. Please contact us for larger donations.")
        
        return amount
    
    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
        cover_fees = cleaned_data.get('cover_fees')
        
        # Calculate processing fee if cover_fees is selected
        if amount and cover_fees:
            processing_fee = self.calculate_processing_fee(amount)
            cleaned_data['processing_fee'] = processing_fee
            cleaned_data['total_amount'] = amount + processing_fee
        else:
            cleaned_data['processing_fee'] = 0
            cleaned_data['total_amount'] = amount
        
        return cleaned_data
    
    def calculate_processing_fee(self, amount):
        """Calculate processing fee based on payment method and amount"""
        # Standard processing fee: 2.9% + $0.30
        percentage_fee = amount * 0.029
        fixed_fee = 0.30
        return round(percentage_fee + fixed_fee, 2)

class DonationSearchForm(forms.Form):
    """Form for searching and filtering donations"""
    
    SORT_CHOICES = [
        ('-created_at', 'Most Recent'),
        ('created_at', 'Oldest First'),
        ('-amount', 'Highest Amount'),
        ('amount', 'Lowest Amount'),
    ]
    
    STATUS_CHOICES = [
        ('', 'All Statuses'),
        ('completed', 'Completed'),
        ('pending', 'Pending'),
        ('failed', 'Failed'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('', 'All Payment Methods'),
        ('paypal', 'PayPal'),
        ('stripe', 'Credit/Debit Card'),
        ('mobile_money', 'Mobile Money'),
        ('bank_transfer', 'Bank Transfer'),
        ('crypto', 'Cryptocurrency'),
    ]
    
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Search by campaign title or donor name...'
        })
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-blue-500'
        })
    )
    
    payment_method = forms.ChoiceField(
        choices=PAYMENT_METHOD_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-blue-500'
        })
    )
    
    min_amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Min amount'
        })
    )
    
    max_amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Max amount'
        })
    )
    
    sort_by = forms.ChoiceField(
        choices=SORT_CHOICES,
        required=False,
        initial='-created_at',
        widget=forms.Select(attrs={
            'class': 'border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-blue-500'
        })
    )

class BulkDonationForm(forms.Form):
    """Form for making donations to multiple campaigns at once"""
    
    campaigns = forms.ModelMultipleChoiceField(
        queryset=Campaign.objects.filter(approved=True),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'campaign-checkbox'
        }),
        help_text="Select campaigns you want to support"
    )
    
    total_amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'w-full border border-gray-300 rounded-md p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            'placeholder': '100.00'
        }),
        help_text="Total amount to distribute among selected campaigns"
    )
    
    DISTRIBUTION_CHOICES = [
        ('equal', 'Equal distribution among all campaigns'),
        ('proportional', 'Proportional to campaign needs'),
        ('custom', 'Custom amounts for each campaign'),
    ]
    
    distribution_method = forms.ChoiceField(
        choices=DISTRIBUTION_CHOICES,
        widget=forms.RadioSelect(),
        initial='equal'
    )
    
    payment_method = forms.ChoiceField(
        choices=DonationForm.PAYMENT_METHODS,
        widget=forms.Select(attrs={
            'class': 'w-full border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-blue-500'
        })
    )
