from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from decimal import Decimal
import uuid
import logging
from .models import Donation, DonationReceipt, Campaign

logger = logging.getLogger(__name__)

class DonationService:
    """Service class to handle donation business logic"""
    
    @staticmethod
    def calculate_processing_fee(amount, payment_method='stripe'):
        """Calculate processing fee based on payment method"""
        fees = {
            'stripe': {'percentage': 0.029, 'fixed': 0.30},
            'paypal': {'percentage': 0.034, 'fixed': 0.30},
            'mobile_money': {'percentage': 0.025, 'fixed': 0.00},
            'bank_transfer': {'percentage': 0.01, 'fixed': 1.00},
            'crypto': {'percentage': 0.015, 'fixed': 0.00},
        }
        
        fee_structure = fees.get(payment_method, fees['stripe'])
        percentage_fee = amount * Decimal(str(fee_structure['percentage']))
        fixed_fee = Decimal(str(fee_structure['fixed']))
        
        return round(percentage_fee + fixed_fee, 2)
    
    @staticmethod
    def process_payment(donation, payment_data):
        """Process payment through appropriate gateway"""
        try:
            # This is a simulation - replace with actual payment gateway integration
            payment_method = donation.payment_method
            
            if payment_method == 'stripe':
                return DonationService._process_stripe_payment(donation, payment_data)
            elif payment_method == 'paypal':
                return DonationService._process_paypal_payment(donation, payment_data)
            elif payment_method == 'mobile_money':
                return DonationService._process_mobile_money_payment(donation, payment_data)
            else:
                # Default processing
                donation.status = 'completed'
                donation.payment_id = f"sim_{uuid.uuid4().hex[:12]}"
                donation.completed_at = timezone.now()
                donation.save()
                return {'success': True, 'payment_id': donation.payment_id}
                
        except Exception as e:
            logger.error(f"Payment processing failed for donation {donation.id}: {str(e)}")
            donation.status = 'failed'
            donation.admin_notes = f"Payment failed: {str(e)}"
            donation.save()
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _process_stripe_payment(donation, payment_data):
        """Process Stripe payment (simulation)"""
        # In real implementation, use Stripe API
        import time
        time.sleep(1)  # Simulate processing time
        
        donation.status = 'completed'
        donation.payment_id = f"stripe_{uuid.uuid4().hex[:12]}"
        donation.completed_at = timezone.now()
        donation.save()
        
        return {'success': True, 'payment_id': donation.payment_id}
    
    @staticmethod
    def _process_paypal_payment(donation, payment_data):
        """Process PayPal payment (simulation)"""
        # In real implementation, use PayPal API
        donation.status = 'completed'
        donation.payment_id = f"paypal_{uuid.uuid4().hex[:12]}"
        donation.completed_at = timezone.now()
        donation.save()
        
        return {'success': True, 'payment_id': donation.payment_id}
    
    @staticmethod
    def _process_mobile_money_payment(donation, payment_data):
        """Process Mobile Money payment (simulation)"""
        # In real implementation, integrate with M-Pesa, Airtel Money, etc.
        donation.status = 'processing'  # Mobile money usually takes time
        donation.payment_id = f"mm_{uuid.uuid4().hex[:12]}"
        donation.save()
        
        return {'success': True, 'payment_id': donation.payment_id, 'status': 'processing'}
    
    @staticmethod
    def generate_receipt(donation):
        """Generate receipt for completed donation"""
        if donation.status != 'completed':
            return None
        
        # Check if receipt already exists
        if hasattr(donation, 'receipt'):
            return donation.receipt
        
        # Generate unique receipt number
        receipt_number = f"EDU-{timezone.now().year}-{uuid.uuid4().hex[:8].upper()}"
        
        receipt = DonationReceipt.objects.create(
            donation=donation,
            receipt_number=receipt_number
        )
        
        return receipt
    
    @staticmethod
    def send_confirmation_email(donation):
        """Send donation confirmation email"""
        try:
            if not donation.donor and not donation.donor_email:
                return False
            
            recipient_email = donation.donor.email if donation.donor else donation.donor_email
            
            context = {
                'donation': donation,
                'campaign': donation.campaign,
                'receipt_data': donation.get_receipt_data(),
            }
            
            subject = f"Thank you for supporting {donation.campaign.title}"
            html_message = render_to_string('emails/donation_confirmation.html', context)
            plain_message = render_to_string('emails/donation_confirmation.txt', context)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient_email],
                html_message=html_message,
                fail_silently=False,
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send confirmation email for donation {donation.id}: {str(e)}")
            return False
    
    @staticmethod
    def send_student_notification(donation):
        """Send notification to student about new donation"""
        try:
            student = donation.campaign.student
            
            context = {
                'donation': donation,
                'campaign': donation.campaign,
                'student': student,
            }
            
            subject = f"New donation received for your campaign: {donation.campaign.title}"
            html_message = render_to_string('emails/student_donation_notification.html', context)
            plain_message = render_to_string('emails/student_donation_notification.txt', context)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[student.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send student notification for donation {donation.id}: {str(e)}")
            return False
    
    @staticmethod
    def process_refund(donation, reason=""):
        """Process donation refund"""
        if not donation.can_be_refunded():
            return {'success': False, 'error': 'Donation cannot be refunded'}
        
        try:
            # In real implementation, process refund through payment gateway
            donation.status = 'refunded'
            donation.admin_notes = f"Refunded: {reason}" if reason else "Refunded"
            donation.save()
            
            # Update campaign amount
            donation.update_campaign_amount()
            
            return {'success': True, 'refund_id': f"refund_{uuid.uuid4().hex[:12]}"}
            
        except Exception as e:
            logger.error(f"Refund processing failed for donation {donation.id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_donation_analytics(campaign=None, date_from=None, date_to=None):
        """Get donation analytics"""
        queryset = Donation.objects.filter(status='completed')
        
        if campaign:
            queryset = queryset.filter(campaign=campaign)
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        from django.db.models import Sum, Avg, Count
        
        analytics = queryset.aggregate(
            total_amount=Sum('net_amount'),
            total_donations=Count('id'),
            average_donation=Avg('net_amount'),
            total_processing_fees=Sum('processing_fee')
        )
        
        # Payment method breakdown
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
        """Create next recurring donation"""
        if not original_donation.is_recurring:
            return None
        
        # Calculate next donation date
        next_date = RecurringDonationService._calculate_next_date(
            original_donation.created_at,
            original_donation.recurring_frequency
        )
        
        # Create new donation
        new_donation = Donation.objects.create(
            amount=original_donation.amount,
            campaign=original_donation.campaign,
            donor=original_donation.donor,
            payment_method=original_donation.payment_method,
            anonymous=original_donation.anonymous,
            is_recurring=True,
            recurring_frequency=original_donation.recurring_frequency,
            parent_donation=original_donation,
            processing_fee=original_donation.processing_fee,
            created_at=next_date
        )
        
        return new_donation
    
    @staticmethod
    def _calculate_next_date(current_date, frequency):
        """Calculate next donation date based on frequency"""
        from dateutil.relativedelta import relativedelta
        
        if frequency == 'monthly':
            return current_date + relativedelta(months=1)
        elif frequency == 'quarterly':
            return current_date + relativedelta(months=3)
        elif frequency == 'yearly':
            return current_date + relativedelta(years=1)
        
        return current_date
    
    @staticmethod
    def process_due_recurring_donations():
        """Process all due recurring donations"""
        from django.utils import timezone
        
        due_donations = Donation.objects.filter(
            is_recurring=True,
            status='pending',
            created_at__lte=timezone.now()
        )
        
        results = []
        for donation in due_donations:
            result = DonationService.process_payment(donation, {})
            results.append({
                'donation_id': donation.id,
                'success': result.get('success', False),
                'error': result.get('error')
            })
        
        return results

class DonationAnalyticsService:
    """Advanced analytics service for donations and campaigns"""
    
    @staticmethod
    def get_platform_analytics():
        """Get platform-wide analytics"""
        from django.db.models import Sum, Avg, Count, Q
        
        # Basic statistics
        total_raised = Donation.objects.filter(status='completed').aggregate(
            Sum('net_amount')
        )['net_amount__sum'] or 0
        
        total_donations = Donation.objects.filter(status='completed').count()
        total_campaigns = Campaign.objects.count()
        active_campaigns = Campaign.objects.filter(approved=True, is_active=True).count()
        successful_campaigns = Campaign.objects.filter(
            current_amount__gte=models.F('goal')
        ).count()
        
        total_donors = Donation.objects.filter(
            status='completed'
        ).values('donor').distinct().count()
        
        # Averages
        avg_campaign_goal = Campaign.objects.aggregate(
            Avg('goal')
        )['goal__avg'] or 0
        
        avg_donation = Donation.objects.filter(status='completed').aggregate(
            Avg('net_amount')
        )['net_amount__avg'] or 0
        
        # Payment method statistics
        payment_method_stats = Donation.objects.filter(status='completed').values(
            'payment_method'
        ).annotate(
            count=Count('id'),
            total=Sum('net_amount')
        ).order_by('-total')
        
        # Category statistics
        category_stats = Campaign.objects.values('category').annotate(
            count=Count('id'),
            total_raised=Sum('current_amount')
        ).order_by('-total_raised')
        
        return {
            'total_raised': total_raised,
            'total_donations': total_donations,
            'total_campaigns': total_campaigns,
            'active_campaigns': active_campaigns,
            'successful_campaigns': successful_campaigns,
            'total_donors': total_donors,
            'average_campaign_goal': avg_campaign_goal,
            'average_donation': avg_donation,
            'payment_method_stats': list(payment_method_stats),
            'category_stats': list(category_stats),
        }
    
    @staticmethod
    def get_campaign_analytics(campaign):
        """Get detailed analytics for a specific campaign"""
        from django.db.models import Sum, Avg, Count
        from django.utils import timezone
        from datetime import timedelta
        
        donations = campaign.donations.filter(status='completed')
        
        # Basic stats
        total_raised = donations.aggregate(Sum('net_amount'))['net_amount__sum'] or 0
        total_donations = donations.count()
        unique_donors = donations.values('donor').distinct().count()
        average_donation = donations.aggregate(Avg('net_amount'))['net_amount__avg'] or 0
        
        # Progress
        progress_percentage = campaign.progress_percentage()
        days_active = (timezone.now() - campaign.created_at).days
        
        # Payment method breakdown
        payment_method_breakdown = donations.values('payment_method').annotate(
            count=Count('id'),
            total=Sum('net_amount')
        ).order_by('-total')
        
        # Recent activity (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_donations = donations.filter(created_at__gte=thirty_days_ago)
        recent_total = recent_donations.aggregate(Sum('net_amount'))['net_amount__sum'] or 0
        recent_count = recent_donations.count()
        
        return {
            'total_raised': total_raised,
            'total_donations': total_donations,
            'unique_donors': unique_donors,
            'average_donation': average_donation,
            'progress_percentage': progress_percentage,
            'days_active': days_active,
            'payment_method_breakdown': list(payment_method_breakdown),
            'recent_activity': {
                'total': recent_total,
                'count': recent_count,
            }
        }
