"""
Service layer for donation processing and business logic
"""
from decimal import Decimal
from django.db import transaction
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from .models import Donation, Campaign, DonationReceipt
import uuid
import logging

logger = logging.getLogger(__name__)

class DonationService:
    """Service class for handling donation operations"""
    
    @staticmethod
    def calculate_processing_fee(amount, payment_method='stripe'):
        """Calculate processing fee based on payment method"""
        fees = {
            'stripe': {'percentage': 0.029, 'fixed': 0.30},
            'paypal': {'percentage': 0.029, 'fixed': 0.30},
            'mobile_money': {'percentage': 0.035, 'fixed': 0.50},
            'bank_transfer': {'percentage': 0.01, 'fixed': 1.00},
            'crypto': {'percentage': 0.015, 'fixed': 0.00},
        }
        
        fee_structure = fees.get(payment_method, fees['stripe'])
        percentage_fee = amount * Decimal(str(fee_structure['percentage']))
        fixed_fee = Decimal(str(fee_structure['fixed']))
        
        return round(percentage_fee + fixed_fee, 2)
    
    @staticmethod
    @transaction.atomic
    def create_donation(campaign, donor, amount, payment_method, **kwargs):
        """Create a new donation with proper validation"""
        
        # Validate campaign
        if not campaign.approved or not campaign.is_active:
            raise ValueError("Campaign is not available for donations")
        
        # Calculate processing fee
        processing_fee = DonationService.calculate_processing_fee(amount, payment_method)
        net_amount = amount - processing_fee
        
        # Create donation
        donation = Donation.objects.create(
            campaign=campaign,
            donor=donor,
            amount=amount,
            payment_method=payment_method,
            processing_fee=processing_fee,
            net_amount=net_amount,
            status='pending',
            **kwargs
        )
        
        logger.info(f"Created donation {donation.id} for ${amount} to campaign {campaign.id}")
        return donation
    
    @staticmethod
    @transaction.atomic
    def process_payment(donation, payment_id=None):
        """Process payment for a donation"""
        
        if donation.status != 'pending':
            raise ValueError(f"Cannot process donation with status: {donation.status}")
        
        try:
            # Update donation status
            donation.status = 'processing'
            donation.payment_id = payment_id
            donation.save()
            
            # Simulate payment processing (replace with actual payment gateway)
            success = DonationService._simulate_payment_processing(donation)
            
            if success:
                donation.status = 'completed'
                donation.completed_at = timezone.now()
                donation.save()
                
                # Generate receipt
                DonationService.generate_receipt(donation)
                
                # Send confirmation emails
                DonationService.send_donation_confirmation(donation)
                
                logger.info(f"Successfully processed donation {donation.id}")
                return True
            else:
                donation.status = 'failed'
                donation.save()
                logger.error(f"Payment processing failed for donation {donation.id}")
                return False
                
        except Exception as e:
            donation.status = 'failed'
            donation.admin_notes = f"Processing error: {str(e)}"
            donation.save()
            logger.error(f"Error processing donation {donation.id}: {str(e)}")
            raise
    
    @staticmethod
    def _simulate_payment_processing(donation):
        """Simulate payment processing (replace with actual gateway integration)"""
        # In a real implementation, this would integrate with:
        # - Stripe API
        # - PayPal API
        # - Mobile money APIs
        # - Bank transfer systems
        # - Cryptocurrency payment processors
        
        # For demo purposes, we'll simulate a 95% success rate
        import random
        return random.random() < 0.95
    
    @staticmethod
    def generate_receipt(donation):
        """Generate a receipt for the donation"""
        receipt_number = f"EDU-{timezone.now().year}-{str(donation.id)[:8].upper()}"
        
        receipt, created = DonationReceipt.objects.get_or_create(
            donation=donation,
            defaults={'receipt_number': receipt_number}
        )
        
        return receipt
    
    @staticmethod
    def send_donation_confirmation(donation):
        """Send confirmation emails to donor and student"""
        
        # Send to donor
        if donation.donor and donation.donor.email:
            try:
                subject = f"Thank you for your donation to {donation.campaign.title}"
                message = render_to_string('emails/donation_confirmation_donor.html', {
                    'donation': donation,
                    'campaign': donation.campaign,
                    'receipt': donation.receipt,
                })
                
                send_mail(
                    subject=subject,
                    message='',
                    html_message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[donation.donor.email],
                    fail_silently=False,
                )
                
                # Update receipt
                if hasattr(donation, 'receipt'):
                    donation.receipt.email_sent = True
                    donation.receipt.email_sent_at = timezone.now()
                    donation.receipt.save()
                    
            except Exception as e:
                logger.error(f"Failed to send donor confirmation for donation {donation.id}: {str(e)}")
        
        # Send to student
        if donation.campaign.student.email:
            try:
                subject = f"New donation received for {donation.campaign.title}"
                message = render_to_string('emails/donation_notification_student.html', {
                    'donation': donation,
                    'campaign': donation.campaign,
                    'student': donation.campaign.student,
                })
                
                send_mail(
                    subject=subject,
                    message='',
                    html_message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[donation.campaign.student.email],
                    fail_silently=False,
                )
                
            except Exception as e:
                logger.error(f"Failed to send student notification for donation {donation.id}: {str(e)}")
    
    @staticmethod
    @transaction.atomic
    def refund_donation(donation, reason=""):
        """Process a refund for a donation"""
        
        if not donation.can_be_refunded():
            raise ValueError("Donation cannot be refunded")
        
        try:
            # Update donation status
            donation.status = 'refunded'
            donation.admin_notes = f"Refunded: {reason}"
            donation.save()
            
            # Update campaign amount
            donation.update_campaign_amount()
            
            # Send refund notification
            DonationService.send_refund_notification(donation, reason)
            
            logger.info(f"Refunded donation {donation.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error refunding donation {donation.id}: {str(e)}")
            raise
    
    @staticmethod
    def send_refund_notification(donation, reason):
        """Send refund notification to donor"""
        if donation.donor and donation.donor.email:
            try:
                subject = f"Refund processed for your donation to {donation.campaign.title}"
                message = render_to_string('emails/refund_notification.html', {
                    'donation': donation,
                    'reason': reason,
                })
                
                send_mail(
                    subject=subject,
                    message='',
                    html_message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[donation.donor.email],
                    fail_silently=False,
                )
                
            except Exception as e:
                logger.error(f"Failed to send refund notification for donation {donation.id}: {str(e)}")
    
    @staticmethod
    def get_donation_analytics(campaign=None, donor=None, date_range=None):
        """Get analytics data for donations"""
        
        queryset = Donation.objects.filter(status='completed')
        
        if campaign:
            queryset = queryset.filter(campaign=campaign)
        
        if donor:
            queryset = queryset.filter(donor=donor)
        
        if date_range:
            start_date, end_date = date_range
            queryset = queryset.filter(created_at__range=[start_date, end_date])
        
        from django.db.models import Sum, Avg, Count
        
        analytics = queryset.aggregate(
            total_amount=Sum('net_amount'),
            average_amount=Avg('net_amount'),
            total_donations=Count('id'),
            unique_donors=Count('donor', distinct=True),
        )
        
        # Add payment method breakdown
        payment_methods = queryset.values('payment_method').annotate(
            count=Count('id'),
            total=Sum('net_amount')
        ).order_by('-total')
        
        analytics['payment_methods'] = payment_methods
        
        return analytics

class RecurringDonationService:
    """Service for handling recurring donations"""
    
    @staticmethod
    def create_recurring_donation(original_donation):
        """Create a recurring donation based on the original"""
        
        if not original_donation.is_recurring:
            raise ValueError("Original donation is not set as recurring")
        
        # Create new donation
        new_donation = Donation.objects.create(
            campaign=original_donation.campaign,
            donor=original_donation.donor,
            amount=original_donation.amount,
            payment_method=original_donation.payment_method,
            processing_fee=original_donation.processing_fee,
            net_amount=original_donation.net_amount,
            anonymous=original_donation.anonymous,
            message=original_donation.message,
            is_recurring=True,
            recurring_frequency=original_donation.recurring_frequency,
            parent_donation=original_donation,
            status='pending'
        )
        
        return new_donation
    
    @staticmethod
    def process_recurring_donations():
        """Process all due recurring donations (called by scheduled task)"""
        
        from datetime import timedelta
        
        # Find recurring donations that are due
        due_donations = Donation.objects.filter(
            is_recurring=True,
            status='completed',
            parent_donation__isnull=True  # Only original recurring donations
        )
        
        processed = 0
        failed = 0
        
        for donation in due_donations:
            try:
                # Check if it's time for next donation
                if RecurringDonationService._is_due_for_renewal(donation):
                    new_donation = RecurringDonationService.create_recurring_donation(donation)
                    
                    # Process the payment
                    if DonationService.process_payment(new_donation):
                        processed += 1
                    else:
                        failed += 1
                        
            except Exception as e:
                logger.error(f"Error processing recurring donation {donation.id}: {str(e)}")
                failed += 1
        
        logger.info(f"Processed {processed} recurring donations, {failed} failed")
        return {'processed': processed, 'failed': failed}
    
    @staticmethod
    def _is_due_for_renewal(donation):
        """Check if a recurring donation is due for renewal"""
        
        if not donation.recurring_frequency:
            return False
        
        # Get the last recurring donation
        last_recurring = donation.recurring_donations.filter(
            status='completed'
        ).order_by('-created_at').first()
        
        reference_date = last_recurring.created_at if last_recurring else donation.created_at
        
        from datetime import timedelta
        now = timezone.now()
        
        if donation.recurring_frequency == 'monthly':
            return now >= reference_date + timedelta(days=30)
        elif donation.recurring_frequency == 'quarterly':
            return now >= reference_date + timedelta(days=90)
        elif donation.recurring_frequency == 'yearly':
            return now >= reference_date + timedelta(days=365)
        
        return False
