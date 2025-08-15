from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
import uuid

class Campaign(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    goal = models.DecimalField(max_digits=10, decimal_places=2)
    current_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='campaigns')
    approved = models.BooleanField(default=False)
    image = models.ImageField(upload_to='campaign_images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # New fields for enhanced functionality
    deadline = models.DateTimeField(null=True, blank=True, help_text="Optional campaign deadline")
    category = models.CharField(max_length=50, choices=[
        ('tuition', 'Tuition & Fees'),
        ('books', 'Books & Supplies'),
        ('living', 'Living Expenses'),
        ('technology', 'Technology & Equipment'),
        ('research', 'Research & Projects'),
        ('travel', 'Study Abroad & Travel'),
        ('other', 'Other Educational Expenses'),
    ], default='tuition')
    
    # Campaign status
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)  # For admin to feature campaigns
    
    # Social sharing
    share_count = models.PositiveIntegerField(default=0)
    view_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['approved', 'is_active']),
            models.Index(fields=['category']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return self.title
    
    def progress_percentage(self):
        if self.goal == 0:
            return 0
        return min(100, int((self.current_amount / self.goal) * 100))
    
    def remaining_amount(self):
        return max(0, self.goal - self.current_amount)
    
    def is_fully_funded(self):
        return self.current_amount >= self.goal
    
    def donor_count(self):
        return self.donations.filter(status='completed').values('donor').distinct().count()
    
    def average_donation(self):
        completed_donations = self.donations.filter(status='completed')
        if completed_donations.exists():
            total = completed_donations.aggregate(models.Sum('amount'))['amount__sum']
            count = completed_donations.count()
            return total / count if count > 0 else 0
        return 0

class Donation(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled'),
    )
    
    PAYMENT_METHOD_CHOICES = (
        ('paypal', 'PayPal'),
        ('stripe', 'Credit/Debit Card'),
        ('credit_card', 'Credit/Debit Card'),
        ('visa', 'Visa'),
        ('mastercard', 'MasterCard'),
        ('amex', 'American Express'),
        ('discover', 'Discover'),
        ('mobile_money', 'Mobile Money'),
        ('bank_transfer', 'Bank Transfer'),
        ('crypto', 'Cryptocurrency'),
    )
    
    # Core donation fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('1.00')), MaxValueValidator(Decimal('10000.00'))]
    )
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='donations')
    donor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='donations'
    )
    
    # Payment information
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='paypal')
    payment_id = models.CharField(max_length=100, blank=True, null=True)  # External payment ID
    
    # Processing fees
    processing_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Donor preferences
    anonymous = models.BooleanField(default=False)
    message = models.TextField(max_length=500, blank=True, help_text="Optional message to the student")
    
    # Recurring donations
    is_recurring = models.BooleanField(default=False)
    recurring_frequency = models.CharField(
        max_length=20,
        choices=[
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('yearly', 'Yearly'),
        ],
        blank=True,
        null=True
    )
    parent_donation = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='recurring_donations'
    )
    
    # Donor information for anonymous donations
    donor_name = models.CharField(max_length=100, blank=True, help_text="Name for anonymous donations")
    donor_email = models.EmailField(blank=True, help_text="Email for anonymous donations")
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Admin fields
    admin_notes = models.TextField(blank=True, help_text="Internal notes for admins")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['donor', 'status']),
            models.Index(fields=['payment_method']),
        ]
    
    def __str__(self):
        donor_name = "Anonymous" if self.anonymous else (self.donor.full_name if self.donor else "Guest")
        return f"${self.amount} from {donor_name} to {self.campaign.title}"
    
    def save(self, *args, **kwargs):
        # Calculate net amount (amount minus processing fee)
        if self.processing_fee:
            self.net_amount = self.amount - self.processing_fee
        else:
            self.net_amount = self.amount
        
        super().save(*args, **kwargs)
        
        # Update campaign amount if donation is completed
        if self.status == 'completed' and self.pk:
            self.update_campaign_amount()
    
    def update_campaign_amount(self):
        """Update the campaign's current amount based on completed donations"""
        total = self.campaign.donations.filter(status='completed').aggregate(
            models.Sum('net_amount')
        )['net_amount__sum'] or 0
        
        self.campaign.current_amount = total
        self.campaign.save(update_fields=['current_amount'])
    
    def get_display_name(self):
        """Get the display name for the donor"""
        if self.anonymous:
            return "Anonymous Donor"
        elif self.donor:
            return self.donor.full_name or self.donor.username
        elif self.donor_name:
            return self.donor_name
        else:
            return "Guest Donor"
    
    def can_be_refunded(self):
        """Check if donation can be refunded"""
        return self.status == 'completed' and self.created_at
    
    def get_receipt_data(self):
        """Get data for donation receipt"""
        return {
            'donation_id': str(self.id),
            'amount': self.amount,
            'processing_fee': self.processing_fee,
            'net_amount': self.net_amount,
            'campaign_title': self.campaign.title,
            'donor_name': self.get_display_name(),
            'payment_method': self.get_payment_method_display(),
            'date': self.completed_at or self.created_at,
            'status': self.get_status_display(),
        }

class DonationReceipt(models.Model):
    """Model to track donation receipts"""
    donation = models.OneToOneField(Donation, on_delete=models.CASCADE, related_name='receipt')
    receipt_number = models.CharField(max_length=50, unique=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Receipt {self.receipt_number} for {self.donation}"

class DonationComment(models.Model):
    """Model for comments/updates on donations"""
    donation = models.ForeignKey(Donation, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    comment = models.TextField()
    is_public = models.BooleanField(default=False)  # Whether visible to donor
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Comment on {self.donation} by {self.author}"


