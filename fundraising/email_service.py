from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class DonationReceiptEmailService:
    """Focused email service for sending donation receipts to donors"""
    
    @staticmethod
    def send_donation_receipt(donation):
        """Send donation receipt email to donor"""
        try:
            # Check if email is configured
            if not settings.EMAIL_HOST_USER:
                logger.warning("Email not configured. Cannot send donation receipt.")
                return False
            
            # Get recipient email
            recipient_email = donation.donor.email if donation.donor else donation.donor_email
            if not recipient_email:
                logger.warning(f"No email address found for donation {donation.id}")
                return False
            
            # Generate receipt data
            receipt_data = {
                'donation': donation,
                'campaign': donation.campaign,
                'donor_name': donation.get_display_name(),
                'receipt_number': f"EDU-{timezone.now().year}-{str(donation.id)[:8].upper()}",
                'site_name': 'EduFund',
                'current_date': timezone.now(),
                'total_amount': donation.amount + (donation.processing_fee or 0),
            }
            
            # Create email subject
            subject = f"Donation Receipt - Thank you for supporting {donation.campaign.title}"
            
            # Render email templates
            html_content = render_to_string('emails/donation_receipt.html', receipt_data)
            text_content = strip_tags(html_content)
            
            # Create email message
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient_email]
            )
            email.attach_alternative(html_content, "text/html")
            
            # Send email
            email.send()
            
            # Update donation receipt tracking
            if hasattr(donation, 'receipt'):
                donation.receipt.email_sent = True
                donation.receipt.email_sent_at = timezone.now()
                donation.receipt.save()
            
            logger.info(f"Donation receipt sent successfully to {recipient_email} for donation {donation.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send donation receipt for donation {donation.id}: {str(e)}")
            return False
    
    @staticmethod
    def send_student_notification(donation):
        """Send notification to student about new donation"""
        try:
            if not settings.EMAIL_HOST_USER:
                logger.warning("Email not configured. Cannot send student notification.")
                return False
            
            student = donation.campaign.student
            
            notification_data = {
                'donation': donation,
                'campaign': donation.campaign,
                'student': student,
                'donor_name': donation.get_display_name(),
                'site_name': 'EduFund',
                'progress_percentage': donation.campaign.progress_percentage(),
            }
            
            subject = f"New donation received for {donation.campaign.title}!"
            
            html_content = render_to_string('emails/student_notification.html', notification_data)
            text_content = strip_tags(html_content)
            
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[student.email]
            )
            email.attach_alternative(html_content, "text/html")
            
            email.send()
            
            logger.info(f"Student notification sent successfully to {student.email} for donation {donation.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send student notification for donation {donation.id}: {str(e)}")
            return False
    
    @staticmethod
    def test_email_configuration():
        """Test email configuration by sending a test email"""
        try:
            if not settings.EMAIL_HOST_USER:
                return {'success': False, 'error': 'Email not configured'}
            
            test_email = EmailMultiAlternatives(
                subject='EduFund Email Test',
                body='This is a test email from EduFund system.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[settings.DEFAULT_FROM_EMAIL]  # Send to self
            )
            
            test_email.send()
            return {'success': True, 'message': 'Test email sent successfully'}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
