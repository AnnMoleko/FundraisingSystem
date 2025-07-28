from django.urls import path
from . import views

urlpatterns = [
    # General pages
    path('', views.home_view, name='home'),
    
    # Dashboard routing based on user role
    path('dashboard/', views.dashboard_redirect, name='dashboard'),
    
    # Campaign routes
    path('campaigns/', views.campaigns_list, name='campaigns_list'),
    path('campaigns/<int:pk>/', views.campaign_detail, name='campaign_detail'),
    path('campaigns/create/', views.campaign_create, name='campaign_create'),
    path('campaigns/<int:pk>/edit/', views.campaign_edit, name='campaign_edit'),
    path('campaigns/<int:pk>/delete/', views.campaign_delete, name='campaign_delete'),
    
    # Student dashboard and routes
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    
    # Admin routes - CUSTOM ADMIN DASHBOARD (not Django admin)
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),  # Changed URL
    path('admin-dashboard/campaigns/', views.admin_campaigns_list, name='admin_campaigns_list'),
    path('admin-dashboard/campaigns/<int:pk>/approve/', views.admin_campaign_approve, name='admin_campaign_approve'),
    path('admin-dashboard/campaigns/<int:pk>/reject/', views.admin_campaign_reject, name='admin_campaign_reject'),
    
    # Donor dashboard and routes
    path('donor/dashboard/', views.donor_dashboard, name='donor_dashboard'),
    
    # Donation routes
    path('campaigns/<int:campaign_id>/donate/', views.make_donation, name='make_donation'),
    path('donations/<int:donation_id>/payment/', views.process_payment, name='process_payment'),
    path('donations/<int:donation_id>/success/', views.donation_success, name='donation_success'),
]
