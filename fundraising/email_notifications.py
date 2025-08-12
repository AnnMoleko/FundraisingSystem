from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)

class EmailNotificationService:
    """Service for sending email notifications related to donations"""
    
    @staticmethod
    def send_donation_confirmation(donation):
        """Send donation confirmation email to donor"""
        try:
            subject = f"Thank you for your donation to {donation.campaign.title}"
            
            # Render HTML email template
            html_message = render_to_string('emails/donation_confirmation.html', {
                'donation': donation,
                'campaign': donation.campaign,
                'donor_name': donation.get_display_name(),
                'site_name': 'EduFund'
            })
            
            # Create plain text version
            plain_message = strip_tags(html_message)
            
            # Send email
            recipient_email = donation.donor.email if donation.donor else donation.donor_email
            
            if recipient_email:
                send_mail(
                    subject=subject,
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient_email],
                    html_message=html_message,
                    fail_silently=False,
                )
                
                logger.info(f"Donation confirmation email sent to {recipient_email} for donation {donation.id}")
                return True
            else:
                logger.warning(f"No email address found for donation {donation.id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send donation confirmation email for donation {donation.id}: {str(e)}")
            return False
    
    @staticmethod
    def send_donation_received_notification(donation):
        """Send notification to student that they received a donation"""
        try:
            subject = f"You received a donation for {donation.campaign.title}!"
            
            html_message = render_to_string('emails/donation_received.html', {
                'donation': donation,
                'campaign': donation.campaign,
                'student': donation.campaign.student,
                'donor_name': donation.get_display_name(),
                'site_name': 'EduFund'
            })
            
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[donation.campaign.student.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Donation received notification sent to {donation.campaign.student.email} for donation {donation.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send donation received notification for donation {donation.id}: {str(e)}")
            return False
    
    @staticmethod
    def send_payment_failed_notification(donation):
        """Send payment failure notification to donor"""
        try:
            subject = f"Payment issue with your donation to {donation.campaign.title}"
            
            html_message = render_to_string('emails/payment_failed.html', {
                'donation': donation,
                'campaign': donation.campaign,
                'donor_name': donation.get_display_name(),
                'site_name': 'EduFund'
            })
            
            plain_message = strip_tags(html_message)
            
            recipient_email = donation.donor.email if donation.donor else donation.donor_email
            
            if recipient_email:
                send_mail(
                    subject=subject,
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient_email],
                    html_message=html_message,
                    fail_silently=False,
                )
                
                logger.info(f"Payment failed notification sent to {recipient_email} for donation {donation.id}")
                return True
            else:
                logger.warning(f"No email address found for failed donation {donation.id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send payment failed notification for donation {donation.id}: {str(e)}")
            return False
