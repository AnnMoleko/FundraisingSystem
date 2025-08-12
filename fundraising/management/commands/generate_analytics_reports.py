from django.core.management.base import BaseCommand
from django.utils import timezone
from fundraising.services import DonationAnalyticsService
from fundraising.models import Campaign
import json

class Command(BaseCommand):
    help = 'Generate analytics report for campaigns and donations'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--campaign-id',
            type=int,
            help='Generate report for specific campaign',
        )
        parser.add_argument(
            '--format',
            choices=['json', 'text'],
            default='text',
            help='Output format',
        )
        parser.add_argument(
            '--output-file',
            help='Save report to file',
        )
    
    def handle(self, *args, **options):
        if options['campaign_id']:
            # Generate campaign-specific report
            try:
                campaign = Campaign.objects.get(id=options['campaign_id'])
                analytics = DonationAnalyticsService.get_campaign_analytics(campaign)
                
                if options['format'] == 'json':
                    report = json.dumps(analytics, indent=2, default=str)
                else:
                    report = self._format_campaign_report(campaign, analytics)
                
            except Campaign.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Campaign {options["campaign_id"]} not found')
                )
                return
        else:
            # Generate platform-wide report
            analytics = DonationAnalyticsService.get_platform_analytics()
            
            if options['format'] == 'json':
                report = json.dumps(analytics, indent=2, default=str)
            else:
                report = self._format_platform_report(analytics)
        
        # Output report
        if options['output_file']:
            with open(options['output_file'], 'w') as f:
                f.write(report)
            self.stdout.write(
                self.style.SUCCESS(f'Report saved to {options["output_file"]}')
            )
        else:
            self.stdout.write(report)
    
    def _format_campaign_report(self, campaign, analytics):
        """Format campaign analytics as text report"""
        return f"""
CAMPAIGN ANALYTICS REPORT
Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

Campaign: {campaign.title}
Student: {campaign.student.full_name}
Created: {campaign.created_at.strftime('%Y-%m-%d')}

FUNDRAISING PROGRESS:
- Goal: ${analytics['total_raised']:,.2f} / ${campaign.goal:,.2f}
- Progress: {analytics['progress_percentage']:.1f}%
- Days Active: {analytics['days_active']}

DONATION STATISTICS:
- Total Donations: {analytics['total_donations']}
- Unique Donors: {analytics['unique_donors']}
- Average Donation: ${analytics['average_donation']:,.2f}

PAYMENT METHOD BREAKDOWN:
{self._format_payment_methods(analytics['payment_method_breakdown'])}
        """.strip()
    
    def _format_platform_report(self, analytics):
        """Format platform analytics as text report"""
        return f"""
PLATFORM ANALYTICS REPORT
Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

OVERALL STATISTICS:
- Total Raised: ${analytics['total_raised']:,.2f}
- Total Donations: {analytics['total_donations']:,}
- Total Campaigns: {analytics['total_campaigns']:,}
- Active Campaigns: {analytics['active_campaigns']:,}
- Successful Campaigns: {analytics['successful_campaigns']:,}
- Total Donors: {analytics['total_donors']:,}

AVERAGES:
- Average Campaign Goal: ${analytics['average_campaign_goal']:,.2f}
- Average Donation: ${analytics['average_donation']:,.2f}

PAYMENT METHOD STATISTICS:
{self._format_payment_methods(analytics['payment_method_stats'])}

CATEGORY BREAKDOWN:
{self._format_categories(analytics['category_stats'])}
        """.strip()
    
    def _format_payment_methods(self, methods):
        """Format payment method statistics"""
        lines = []
        for method in methods:
            lines.append(
                f"- {method['payment_method']}: {method['count']} donations "
                f"(${method['total']:,.2f})"
            )
        return '\n'.join(lines) if lines else "No data available"
    
    def _format_categories(self, categories):
        """Format category statistics"""
        lines = []
        for category in categories:
            lines.append(
                f"- {category['category']}: {category['count']} campaigns "
                f"(${category['total_raised']:,.2f} raised)"
            )
        return '\n'.join(lines) if lines else "No data available"
