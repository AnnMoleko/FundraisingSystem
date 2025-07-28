from django.contrib import admin
from .models import Campaign, Donation

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ['title', 'student', 'goal', 'current_amount', 'approved', 'created_at']
    list_filter = ['approved', 'created_at']
    search_fields = ['title', 'student__username', 'student__full_name']
    readonly_fields = ['current_amount', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Campaign Info', {
            'fields': ('title', 'description', 'goal', 'current_amount', 'image')
        }),
        ('Management', {
            'fields': ('student', 'approved')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ['campaign', 'donor', 'amount', 'status', 'payment_method', 'created_at']
    list_filter = ['status', 'payment_method', 'anonymous', 'created_at']
    search_fields = ['campaign__title', 'donor__username']
    readonly_fields = ['created_at', 'updated_at']
