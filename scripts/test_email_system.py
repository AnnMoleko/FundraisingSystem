#!/usr/bin/env python
"""
Test script for the EduFund email system
"""
import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edufund_project.settings')
django.setup()

from fundraising.email_service import DonationReceiptEmailService
from fundraising.models import Donation, Campaign
from authentication.models import User
from django.conf import settings

def test_email_configuration():
    """Test basic email configuration"""
    print("Testing email configuration...")
    
    result = DonationReceiptEmailService.test_email_configuration()
    
    if result['success']:
        print("✅ Email configuration test passed!")
        print(f"   Message: {result['message']}")
    else:
        print("❌ Email configuration test failed!")
        print(f"   Error: {result['error']}")
        print("\n📋 To fix email configuration:")
        print("   1. Set EMAIL_HOST_USER in your environment variables")
        print("   2. Set EMAIL_HOST_PASSWORD in your environment variables")
        print("   3. Configure EMAIL_HOST and EMAIL_PORT in settings.py")
    
    return result['success']

def test_donation_receipt_email():
    """Test sending a donation receipt email"""
    print("\nTesting donation receipt email...")
    
    try:
        # Find a completed donation to test with
        donation = Donation.objects.filter(status='completed').first()
        
        if not donation:
            print("❌ No completed donations found to test with")
            return False
        
        print(f"   Using donation: {donation.id}")
        print(f"   Campaign: {donation.campaign.title}")
        print(f"   Amount: ${donation.amount}")
        
        # Send test email
        success = DonationReceiptEmailService.send_donation_receipt(donation)
        
        if success:
            print("✅ Donation receipt email sent successfully!")
            recipient = donation.donor.email if donation.donor else donation.donor_email
            print(f"   Sent to: {recipient}")
        else:
            print("❌ Failed to send donation receipt email")
        
        return success
        
    except Exception as e:
        print(f"❌ Error testing donation receipt email: {str(e)}")
        return False

def main():
    """Main test function"""
    print("🧪 EduFund Email System Test")
    print("=" * 40)
    
    # Test email configuration
    config_ok = test_email_configuration()
    
    if config_ok:
        # Test donation receipt email
        test_donation_receipt_email()
    else:
        print("\n⚠️  Skipping email sending tests due to configuration issues")
    
    print("\n" + "=" * 40)
    print("Email system test completed!")

if __name__ == "__main__":
    main()
