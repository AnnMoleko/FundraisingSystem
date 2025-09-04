from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse
from django.db.models import Sum, Count, Q, F
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.conf import settings
import json
import logging
from django.utils import timezone
import stripe
import hashlib
import hmac
from uuid import UUID

from .models import Campaign, Donation
from authentication.models import User
from .forms import CampaignForm, DonationForm
from .decorators import student_required, donor_required, admin_required, secure_payment_view, log_payment_activity
from .payment_gateways import PaymentGatewayFactory, PaymentGatewayError
from .email_service import DonationReceiptEmailService
from .security import WebhookSecurityValidator, DonationValidator

logger = logging.getLogger(__name__)

def home_view(request):
    # Get only approved campaigns for the home page
    approved_campaigns = Campaign.objects.filter(approved=True).order_by('-created_at')[:3]
    
    # Get some statistics for the home page
    total_raised = Donation.objects.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
    total_students_helped = Campaign.objects.filter(approved=True, current_amount__gt=0).count()
    total_donors = User.objects.filter(role='donor', donations__isnull=False).distinct().count()
    
    context = {
        'campaigns': approved_campaigns,
        'total_raised': total_raised,
        'total_students_helped': total_students_helped,
        'total_donors': total_donors,
    }
    return render(request, 'authentication/home.html', context)

@login_required
def dashboard_redirect(request):
    """Redirect users to their appropriate dashboard based on role"""
    if request.user.role == 'student':
        return redirect('student_dashboard')
    elif request.user.role == 'donor':
        return redirect('donor_dashboard')
    elif request.user.role == 'admin':
        return redirect('admin_dashboard')
    else:
        return redirect('home')

# Campaign Views
@login_required
def campaigns_list(request):
    # Show approved campaigns for everyone
    campaigns = Campaign.objects.filter(approved=True).order_by('-created_at')
    return render(request, 'campaigns/list.html', {'campaigns': campaigns})

@login_required
def campaign_detail(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    
    # Only approved campaigns are visible to everyone
    # Students can see their own campaigns even if not approved
    # Admins can see all campaigns
    if not campaign.approved and request.user.role != 'admin' and campaign.student != request.user:
        return HttpResponseForbidden("You don't have permission to view this campaign.")
    
    # For donors, include the donation form
    donation_form = None
    if request.user.role == 'donor':
        donation_form = DonationForm()
        
    donations = Donation.objects.filter(campaign=campaign, status='completed', anonymous=False).order_by('-created_at')
    
    context = {
        'campaign': campaign,
        'donation_form': donation_form,
        'donations': donations,
    }
    return render(request, 'campaigns/detail.html', context)

@login_required
@student_required
def campaign_create(request):
    if request.method == 'POST':
        form = CampaignForm(request.POST, request.FILES)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.student = request.user
            campaign.save()
            
            messages.success(
                request, 
                f"🎉 Your campaign '{campaign.title}' has been created successfully! "
                "It's now pending admin approval and will be visible to donors once approved."
            )
            return redirect('student_dashboard')
        else:
            messages.error(request, "Please correct the errors below and try again.")
    else:
        form = CampaignForm()
    
    return render(request, 'campaigns/create.html', {'form': form})

@login_required
@student_required
def campaign_edit(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk, student=request.user)
    
    if request.method == 'POST':
        form = CampaignForm(request.POST, request.FILES, instance=campaign)
        if form.is_valid():
            campaign = form.save(commit=False)
            # If the campaign was already approved, editing will require re-approval
            if campaign.approved:
                campaign.approved = False
                messages.info(request, "Your campaign will need to be re-approved since you've made changes.")
            campaign.save()
            messages.success(request, "Your campaign has been updated.")
            return redirect('student_dashboard')
    else:
        form = CampaignForm(instance=campaign)
    
    return render(request, 'campaigns/edit.html', {'form': form, 'campaign': campaign})

@login_required
@student_required
def campaign_delete(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk, student=request.user)
    
    if request.method == 'POST':
        campaign.delete()
        messages.success(request, "Your campaign has been deleted.")
        return redirect('student_dashboard')
    
    return render(request, 'campaigns/delete.html', {'campaign': campaign})

# Admin Views
@login_required
@admin_required
def admin_dashboard(request):
    # Get statistics for admin dashboard
    total_campaigns = Campaign.objects.count()
    pending_campaigns = Campaign.objects.filter(approved=False).count()
    total_users = User.objects.count()
    total_raised = Donation.objects.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Get recent campaigns that need approval
    campaigns_for_approval = Campaign.objects.filter(approved=False).order_by('-created_at')[:5]
    
    context = {
        'total_campaigns': total_campaigns,
        'pending_campaigns': pending_campaigns,
        'total_users': total_users,
        'total_raised': total_raised,
        'campaigns_for_approval': campaigns_for_approval,
    }
    return render(request, 'dashboards/admin.html', context)

@login_required
@admin_required
def admin_campaigns_list(request):
    # Default to pending campaigns
    filter_status = request.GET.get('status', 'pending')
    
    if filter_status == 'approved':
        campaigns = Campaign.objects.filter(approved=True).order_by('-created_at')
    else:  # pending
        campaigns = Campaign.objects.filter(approved=False).order_by('-created_at')
    
    return render(request, 'admin/campaigns_list.html', {
        'campaigns': campaigns,
        'filter_status': filter_status
    })

@login_required
@admin_required
def admin_campaign_approve(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    
    if request.method == 'POST':
        campaign.approved = True
        campaign.save()
        messages.success(request, f"Campaign '{campaign.title}' has been approved.")
        return redirect('admin_campaigns_list')
    
    return render(request, 'admin/campaign_approve.html', {'campaign': campaign})

@login_required
@admin_required
def admin_campaign_reject(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    
    if request.method == 'POST':
        campaign.delete()
        messages.success(request, f"Campaign '{campaign.title}' has been rejected and deleted.")
        return redirect('admin_campaigns_list')
    
    return render(request, 'admin/campaign_reject.html', {'campaign': campaign})

@login_required
@admin_required
def process_manual_payment(request, donation_id:UUID):
    """Admin function to manually process payments for non-automated methods"""
    donation = get_object_or_404(Donation, pk=donation_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'approve':
            # Manually approve payment
            donation.status = 'completed'
            donation.completed_at = timezone.now()
            donation.save()
            
            # Update campaign amount
            donation.update_campaign_amount()
            
            # Send confirmation emails
            DonationReceiptEmailService.send_donation_confirmation(donation)
            DonationReceiptEmailService.send_donation_received_notification(donation)
            
            messages.success(request, f"Payment for donation {donation.id} has been approved.")
            
        elif action == 'reject':
            # Reject payment
            donation.status = 'failed'
            donation.save()
            
            # Send failure notification
            # Send failure notification using new email service
            try:
                DonationReceiptEmailService.send_donation_receipt(donation)
                logger.info(f"Payment failure notification sent for donation {donation.id}")
            except Exception as e:
                logger.error(f"Failed to send payment failure notification: {str(e)}")
            
            messages.success(request, f"Payment for donation {donation.id} has been rejected.")
        return redirect('donations_list')
    
    return render(request, 'admin/process_manual_payment.html', {'donation': donation})

@login_required
@admin_required
def donations_list(request):
    """Admin view to list and manage donations"""
    status_filter = request.GET.get('status', 'all')
    payment_method_filter = request.GET.get('payment_method', 'all')
    
    donations = Donation.objects.select_related('donor', 'campaign', 'campaign__student').order_by('-created_at')
    
    # Apply filters
    if status_filter != 'all':
        donations = donations.filter(status=status_filter)
    
    if payment_method_filter != 'all':
        donations = donations.filter(payment_method=payment_method_filter)
    
    # Get statistics
    total_donations = donations.count()
    total_amount = donations.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
    pending_count = donations.filter(status='pending').count()
    
    context = {
        'donations': donations[:50],  # Limit to 50 for performance
        'status_filter': status_filter,
        'payment_method_filter': payment_method_filter,
        'total_donations': total_donations,
        'total_amount': total_amount,
        'pending_count': pending_count,
        'status_choices': Donation.STATUS_CHOICES,
        'payment_method_choices': Donation.PAYMENT_METHOD_CHOICES,
    }
    
    return render(request, 'admin/donations_list.html', context)

@login_required
@admin_required
def refund_donation(request, donation_id:UUID):
    """Admin function to process refunds"""
    donation = get_object_or_404(Donation, pk=donation_id)
    
    if donation.status != 'completed':
        messages.error(request, "Only completed donations can be refunded.")
        return redirect('admin_donations_list')
    
    if request.method == 'POST':
        try:
            refund_amount = float(request.POST.get('refund_amount', donation.amount))
            reason = request.POST.get('reason', '')
            
            # Process refund through payment gateway
            if donation.payment_method in ['stripe', 'credit_card']:
                gateway = PaymentGatewayFactory.get_gateway('stripe')
                result = gateway.create_refund(donation.payment_id, refund_amount)
                
                if result['success']:
                    # Update donation status and amount
                    donation.status = 'refunded'
                    donation.admin_notes = f"Refunded ${refund_amount}. Reason: {reason}"
                    donation.save()
                    
                    # Update campaign amount
                    donation.update_campaign_amount()
                    
                    messages.success(request, f"Refund of ${refund_amount} processed successfully.")
                else:
                    messages.error(request, f"Refund failed: {result['error']}")
                    
            elif donation.payment_method == 'paypal':
                gateway = PaymentGatewayFactory.get_gateway('paypal')
                result = gateway.create_refund(donation.payment_id, refund_amount)
                
                if result['success']:
                    # Update donation status and amount
                    donation.status = 'refunded'
                    donation.admin_notes = f"Refunded R{refund_amount}. Reason: {reason}"
                    donation.save()
                    
                    # Update campaign amount
                    donation.update_campaign_amount()
                    
                    messages.success(request, f"PayPal refund of R{refund_amount} processed successfully.")
                else:
                    messages.error(request, f"PayPal refund failed: {result['error']}")
            
            else:
                # Manual refund for other payment methods
                donation.status = 'refunded'
                donation.admin_notes = f"Manual refund of R{refund_amount}. Reason: {reason}"
                donation.save()
                
                # Update campaign amount
                donation.update_campaign_amount()
                
                messages.success(request, f"Manual refund of R{refund_amount} recorded. Please process the actual refund manually.")
            
        except Exception as e:
            logger.error(f"Refund processing error: {str(e)}")
            messages.error(request, f"Refund processing failed: {str(e)}")
        
        return redirect('admin_donations_list')
    
    return render(request, 'admin/refund_donation.html', {'donation': donation})

# Student Dashboard
@login_required
@student_required
def student_dashboard(request):
    # Get all campaigns created by the student
    campaigns = Campaign.objects.filter(student=request.user).order_by('-created_at')
    
    # Calculate detailed stats
    approved_campaigns = campaigns.filter(approved=True)
    pending_campaigns = campaigns.filter(approved=False)
    total_raised = campaigns.aggregate(Sum('current_amount'))['current_amount__sum'] or 0
    total_goal = campaigns.aggregate(Sum('goal'))['goal__sum'] or 0
    
    # Calculate total supporters (unique donors across all campaigns)
    total_supporters = Donation.objects.filter(
        campaign__in=campaigns,
        status='completed'
    ).values('donor').distinct().count()
    
    context = {
        'campaigns': campaigns,
        'approved_campaigns_count': approved_campaigns.count(),
        'pending_campaigns_count': pending_campaigns.count(),
        'total_raised': total_raised,
        'total_goal': total_goal,
        'total_supporters': total_supporters,
        'has_campaigns': campaigns.exists(),
    }
    return render(request, 'dashboards/student.html', context)

# Donor Views
@login_required
@donor_required
def donor_dashboard(request):
    # Get all donations made by the donor
    donations = Donation.objects.filter(donor=request.user).order_by('-created_at')
    completed_donations = donations.filter(status='completed')
    
    # Calculate comprehensive stats
    total_donated = completed_donations.aggregate(Sum('amount'))['amount__sum'] or 0
    campaigns_supported = completed_donations.values('campaign').distinct().count()
    
    # Calculate students helped (unique students from campaigns donated to)
    students_helped = completed_donations.values('campaign__student').distinct().count()
    
    # Calculate impact score (percentage of campaigns that reached their goal after donation)
    campaigns_with_donations = completed_donations.values_list('campaign', flat=True).distinct()
    successful_campaigns = Campaign.objects.filter(
        id__in=campaigns_with_donations,
        current_amount__gte=F('goal')
    ).count()
    impact_score = int((successful_campaigns / campaigns_supported * 100)) if campaigns_supported > 0 else 0
    
    # Get recent donations (last 5 completed donations)
    recent_donations = completed_donations.select_related('campaign', 'campaign__student')[:5]
    
    # Get recommended campaigns (approved campaigns the donor hasn't donated to)
    donated_campaign_ids = donations.values_list('campaign', flat=True)
    recommended_campaigns = Campaign.objects.filter(
        approved=True
    ).exclude(
        id__in=donated_campaign_ids
    ).select_related('student').order_by('-created_at')[:6]
    
    context = {
        'donations': donations,
        'recent_donations': recent_donations,
        'total_donated': total_donated,
        'campaigns_supported': campaigns_supported,
        'students_helped': students_helped,
        'impact_score': impact_score,
        'recommended_campaigns': recommended_campaigns,
        'has_donations': completed_donations.exists(),
    }
    return render(request, 'dashboards/donor.html', context)

@login_required
@donor_required
@secure_payment_view
def make_donation(request, campaign_id):
    campaign = get_object_or_404(Campaign, pk=campaign_id, approved=True)
    
    if request.method == 'POST':
        form = DonationForm(request.POST, campaign=campaign)
        if form.is_valid():
            # Added security validation check
            if hasattr(request, 'security_validation'):
                validation = request.security_validation
                if validation['fraud_analysis']['requires_review']:
                    messages.warning(
                        request, 
                        "Your donation has been flagged for manual review. "
                        "You will receive an email confirmation once it's processed."
                    )
            
            donation = form.save(commit=False)
            donation.campaign = campaign
            donation.donor = request.user
            donation.status = 'pending'
            
            # Calculate processing fee if cover_fees is selected
            if form.cleaned_data.get('cover_fees'):
                donation.processing_fee = form.cleaned_data.get('processing_fee', 0)
            
            # Store security metadata
            if hasattr(request, 'security_validation'):
                metadata = request.security_validation['metadata']
                donation.ip_address = metadata.get('ip_address')
                donation.user_agent = metadata.get('user_agent')
            
            donation.save()
            
            return redirect(reverse('process_payment', args=[donation.id]))
    else:
        form = DonationForm(campaign=campaign)
    
    return render(request, 'donations/make_donation.html', {
        'form': form,
        'campaign': campaign,
    })

@login_required
@donor_required
@secure_payment_view
def process_payment(request, donation_id: UUID):
    donation = get_object_or_404(Donation, pk=donation_id, donor=request.user)
    
    if donation.status == 'completed':
        return redirect('donation_success', donation_id=donation.id)
    
    if request.method == 'POST':
        try:
            payment_method = donation.payment_method
            total_amount = donation.amount + (donation.processing_fee or 0)
            
            # Prepare payment metadata
            metadata = {
                'donation_id': str(donation.id),
                'campaign_id': str(donation.campaign.id),
                'donor_id': str(donation.donor.id),
                'campaign_title': donation.campaign.title
            }
            
            if payment_method in ['stripe', 'credit_card']:
                # Process Stripe payment
                gateway = PaymentGatewayFactory.get_gateway('stripe')
                result = gateway.create_payment_intent(
                    amount=total_amount,
                    metadata=metadata
                )
                
                if result['success']:
                    donation.payment_id = result['payment_intent_id']
                    donation.status = 'processing'
                    donation.save()
                    
                    # Return JSON for frontend to handle Stripe confirmation
                    return JsonResponse({
                        'success': True,
                        'client_secret': result['client_secret'],
                        'payment_method': 'stripe'
                    })
                else:
                    messages.error(request, f"Payment failed: {result['error']}")
                    
            elif payment_method == 'paypal':
                # Process PayPal payment
                gateway = PaymentGatewayFactory.get_gateway('paypal')
                
                return_url = request.build_absolute_uri(
                    reverse('paypal_return', args=[donation.id])
                )
                cancel_url = request.build_absolute_uri(
                    reverse('paypal_cancel', args=[donation.id])
                )
                
                result = gateway.create_payment(
                    amount=total_amount,
                    return_url=return_url,
                    cancel_url=cancel_url,
                    description=f"Donation to {donation.campaign.title}"
                )
                
                if result['success']:
                    donation.payment_id = result['payment_id']
                    donation.status = 'processing'
                    donation.save()
                    
                    return redirect(result['approval_url'])
                else:
                    messages.error(request, f"PayPal payment failed: {result['error']}")
            
            else:
                # For now, mark as pending and require manual verification
                donation.status = 'pending'
                donation.save()
                
                messages.info(
                    request, 
                    f"Payment method {donation.get_payment_method_display()} requires manual processing. "
                    "You will receive instructions via email."
                )
                return redirect('donation_success', donation_id=donation.id)
                
        except PaymentGatewayError as e:
            logger.error(f"Payment gateway error: {str(e)}")
            messages.error(request, f"Payment processing error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected payment error: {str(e)}")
            messages.error(request, "An unexpected error occurred. Please try again.")
    
    context = {
        'donation': donation,
        'stripe_publishable_key': getattr(settings, 'STRIPE_PUBLISHABLE_KEY', ''),
        'total_amount': donation.amount + (donation.processing_fee or 0)
    }
    return render(request, 'donations/process_payment.html', context)

@login_required
def paypal_return(request, donation_id):
    """Handle PayPal payment return"""
    donation = get_object_or_404(Donation, pk=donation_id, donor=request.user)
    
    payment_id = request.GET.get('paymentId')
    payer_id = request.GET.get('PayerID')
    
    if payment_id and payer_id:
        try:
            gateway = PaymentGatewayFactory.get_gateway('paypal')
            result = gateway.execute_payment(payment_id, payer_id)
            
            if result['success']:
                donation.status = 'completed'
                donation.completed_at = timezone.now()
                donation.save()
                
                # Update campaign amount
                donation.update_campaign_amount()
                
                messages.success(
                    request, 
                    f"Thank you for your donation of ${donation.amount} to {donation.campaign.title}!"
                )
                return redirect('donation_success', donation_id=donation.id)
            else:
                messages.error(request, f"Payment execution failed: {result['error']}")
                donation.status = 'failed'
                donation.save()
                
        except Exception as e:
            logger.error(f"PayPal return error: {str(e)}")
            messages.error(request, "Payment processing failed. Please contact support.")
            donation.status = 'failed'
            donation.save()
    
    return redirect('process_payment', donation_id=donation.id)

@login_required
def paypal_cancel(request, donation_id):
    """Handle PayPal payment cancellation"""
    donation = get_object_or_404(Donation, pk=donation_id, donor=request.user)
    
    donation.status = 'cancelled'
    donation.save()
    
    messages.info(request, "Payment was cancelled. You can try again anytime.")
    return redirect('process_payment', donation_id=donation.id)

@login_required
def donation_success(request, donation_id):
    donation = get_object_or_404(Donation, pk=donation_id)
    
    # Only the donor or an admin can view this page
    if donation.donor != request.user and request.user.role != 'admin':
        return HttpResponseForbidden("You don't have permission to view this page.")
    
    return render(request, 'donations/success.html', {'donation': donation})

# Custom Error Views
def custom_404(request, exception):
    return render(request, 'errors/404.html', status=404)

def custom_500(request):
    return render(request, 'errors/500.html', status=500)

def custom_403(request, exception):
    return render(request, 'errors/403.html', status=403)

@csrf_exempt
@require_POST
@log_payment_activity("stripe_webhook")
def stripe_webhook(request):
    """Handle Stripe webhook events"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
    
    # Added webhook security validation
    if not WebhookSecurityValidator.validate_stripe_webhook(payload, sig_header, endpoint_secret):
        WebhookSecurityValidator.log_webhook_attempt(
            'stripe', 
            request.META.get('REMOTE_ADDR', 'unknown'), 
            success=False
        )
        return HttpResponse(status=400)
    
    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        logger.error("Invalid payload in Stripe webhook")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid signature in Stripe webhook")
        return HttpResponse(status=400)
    
    # Handle the event
    try:
        if event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            donation_id = payment_intent.get('metadata', {}).get('donation_id')
            
            if donation_id:
                try:
                    donation = Donation.objects.get(id=donation_id)
                    
                    # Update donation status to completed
                    donation.status = 'completed'
                    donation.completed_at = timezone.now()
                    donation.payment_id = payment_intent['id']
                    donation.save()
                    
                    # Update campaign amount
                    donation.update_campaign_amount()
                    
                    # Send confirmation emails
                    EmailNotificationService.send_donation_confirmation(donation)
                    EmailNotificationService.send_donation_received_notification(donation)
                    
                    logger.info(f"Stripe payment succeeded for donation {donation_id}")
                    
                except Donation.DoesNotExist:
                    logger.error(f"Donation {donation_id} not found for Stripe webhook")
            
        elif event['type'] == 'payment_intent.payment_failed':
            payment_intent = event['data']['object']
            donation_id = payment_intent.get('metadata', {}).get('donation_id')
            
            if donation_id:
                try:
                    donation = Donation.objects.get(id=donation_id)
                    
                    # Update donation status to failed
                    donation.status = 'failed'
                    donation.save()
                    
                    # Send failure notification
                    EmailNotificationService.send_payment_failed_notification(donation)
                    
                    logger.info(f"Stripe payment failed for donation {donation_id}")
                    
                except Donation.DoesNotExist:
                    logger.error(f"Donation {donation_id} not found for Stripe webhook")
        
        elif event['type'] == 'payment_intent.canceled':
            payment_intent = event['data']['object']
            donation_id = payment_intent.get('metadata', {}).get('donation_id')
            
            if donation_id:
                try:
                    donation = Donation.objects.get(id=donation_id)
                    
                    # Update donation status to cancelled
                    donation.status = 'cancelled'
                    donation.save()
                    
                    logger.info(f"Stripe payment cancelled for donation {donation_id}")
                    
                except Donation.DoesNotExist:
                    logger.error(f"Donation {donation_id} not found for Stripe webhook")
        
        else:
            logger.info(f"Unhandled Stripe webhook event type: {event['type']}")
        
        # Log successful webhook processing
        WebhookSecurityValidator.log_webhook_attempt(
            'stripe', 
            request.META.get('REMOTE_ADDR', 'unknown'), 
            success=True
        )
    
    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {str(e)}")
        WebhookSecurityValidator.log_webhook_attempt(
            'stripe', 
            request.META.get('REMOTE_ADDR', 'unknown'), 
            success=False
        )
        return HttpResponse(status=500)
    
    return HttpResponse(status=200)

@csrf_exempt
@require_POST
@log_payment_activity("paypal_webhook")
def paypal_webhook(request):
    """Handle PayPal webhook events (IPN - Instant Payment Notification)"""
    try:
        # Get the raw POST data
        raw_data = request.body.decode('utf-8')
        
        # Added webhook security validation
        if not WebhookSecurityValidator.validate_paypal_webhook(raw_data, request.META):
            WebhookSecurityValidator.log_webhook_attempt(
                'paypal', 
                request.META.get('REMOTE_ADDR', 'unknown'), 
                success=False
            )
            logger.error("PayPal webhook verification failed")
            return HttpResponse(status=400)
        
        # Parse the data
        data = {}
        for line in raw_data.split('&'):
            if '=' in line:
                key, value = line.split('=', 1)
                data[key] = value
        
        payment_status = data.get('payment_status', '').lower()
        custom_data = data.get('custom', '')  # This should contain our donation ID
        txn_id = data.get('txn_id', '')
        
        if custom_data:
            try:
                donation = Donation.objects.get(id=custom_data)
                
                if payment_status == 'completed':
                    # Update donation status to completed
                    donation.status = 'completed'
                    donation.completed_at = timezone.now()
                    donation.payment_id = txn_id
                    donation.save()
                    
                    # Update campaign amount
                    donation.update_campaign_amount()
                    
                    # Send confirmation emails
                    DonationReceiptEmailService.send_donation_confirmation(donation)
                    DonationReceiptEmailService.send_donation_received_notification(donation)
                    
                    logger.info(f"PayPal payment completed for donation {custom_data}")
                
                elif payment_status in ['failed', 'denied', 'expired']:
                    # Update donation status to failed
                    donation.status = 'failed'
                    donation.save()
                    
                    # Send failure notification
                    DonationReceiptEmailService.send_payment_failed_notification(donation)
                    
                    logger.info(f"PayPal payment failed for donation {custom_data}")
                
                elif payment_status == 'refunded':
                    # Update donation status to refunded
                    donation.status = 'refunded'
                    donation.save()
                    
                    # Update campaign amount (subtract the refunded amount)
                    donation.update_campaign_amount()
                    
                    logger.info(f"PayPal payment refunded for donation {custom_data}")
                
            except Donation.DoesNotExist:
                logger.error(f"Donation {custom_data} not found for PayPal webhook")
        
        # Log successful webhook processing
        WebhookSecurityValidator.log_webhook_attempt(
            'paypal', 
            request.META.get('REMOTE_ADDR', 'unknown'), 
            success=True
        )
        
    except Exception as e:
        logger.error(f"Error processing PayPal webhook: {str(e)}")
        WebhookSecurityValidator.log_webhook_attempt(
            'paypal', 
            request.META.get('REMOTE_ADDR', 'unknown'), 
            success=False
        )
        return HttpResponse(status=500)
    
    return HttpResponse(status=200)
