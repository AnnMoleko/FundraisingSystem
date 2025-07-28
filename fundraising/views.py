from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponseForbidden
from django.db.models import Sum, Count, Q
from .models import Campaign, Donation
from authentication.models import User
from .forms import CampaignForm, DonationForm
from .decorators import student_required, donor_required, admin_required

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
            messages.success(request, "Your campaign has been submitted for approval.")
            return redirect('student_dashboard')
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

# Student Dashboard
@login_required
@student_required
def student_dashboard(request):
    # Get all campaigns created by the student
    campaigns = Campaign.objects.filter(student=request.user).order_by('-created_at')
    
    # Calculate some stats
    approved_campaigns = campaigns.filter(approved=True).count()
    total_raised = campaigns.aggregate(Sum('current_amount'))['current_amount__sum'] or 0
    
    context = {
        'campaigns': campaigns,
        'approved_campaigns': approved_campaigns,
        'total_raised': total_raised,
    }
    return render(request, 'dashboards/student.html', context)

# Donor Views
@login_required
@donor_required
def donor_dashboard(request):
    # Get all donations made by the donor
    donations = Donation.objects.filter(donor=request.user).order_by('-created_at')
    
    # Calculate some stats
    total_donated = donations.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
    campaigns_supported = donations.filter(status='completed').values('campaign').distinct().count()
    
    # Get recommended campaigns (just get most recent approved ones that the donor hasn't donated to)
    donated_campaign_ids = donations.values_list('campaign', flat=True)
    recommended_campaigns = Campaign.objects.filter(approved=True).exclude(id__in=donated_campaign_ids).order_by('-created_at')[:3]
    
    context = {
        'donations': donations,
        'total_donated': total_donated,
        'campaigns_supported': campaigns_supported,
        'recommended_campaigns': recommended_campaigns,
    }
    return render(request, 'dashboards/donor.html', context)

# Donation Views
@login_required
@donor_required
def make_donation(request, campaign_id):
    campaign = get_object_or_404(Campaign, pk=campaign_id, approved=True)
    
    if request.method == 'POST':
        form = DonationForm(request.POST)
        if form.is_valid():
            donation = form.save(commit=False)
            donation.campaign = campaign
            donation.donor = request.user
            donation.status = 'pending'  # Start with pending status
            donation.save()
            
            # Redirect to payment processing
            return redirect(reverse('process_payment', args=[donation.id]))
    else:
        form = DonationForm()
    
    return render(request, 'donations/make_donation.html', {
        'form': form,
        'campaign': campaign,
    })

@login_required
@donor_required
def process_payment(request, donation_id):
    donation = get_object_or_404(Donation, pk=donation_id, donor=request.user)
    
    if request.method == 'POST':
        # In a real app, this is where you would integrate with payment gateways
        # For now, we'll just mark the payment as complete
        donation.status = 'completed'
        donation.save()
        
        # Update campaign amount
        campaign = donation.campaign
        campaign.current_amount += donation.amount
        campaign.save()
        
        messages.success(request, f"Thank you for your donation of ${donation.amount} to {campaign.title}!")
        return redirect('donation_success', donation_id=donation.id)
    
    return render(request, 'donations/process_payment.html', {'donation': donation})

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

