from django.core.management.base import BaseCommand
from django.utils import timezone
from fundraising.services import RecurringDonationService
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Process recurring donations that are due'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without actually processing',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS(
                f'Starting recurring donation processing at {timezone.now()}'
            )
        )
        
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No actual processing will occur')
            )
            # TODO: Implement dry run logic
            return
        
        try:
            processed_count = RecurringDonationService.process_recurring_donations()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully processed {processed_count} recurring donations'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error processing recurring donations: {str(e)}')
            )
            logger.error(f'Recurring donation processing failed: {str(e)}')
