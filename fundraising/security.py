from django.core.cache import cache
from django.http import HttpResponseForbidden
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
import hashlib
import hmac
import re
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

class PaymentSecurityValidator:
    """Security validation for payment processing"""
    
    # Suspicious patterns in donation messages
    SUSPICIOUS_PATTERNS = [
        r'test\s*payment',
        r'fake\s*donation',
        r'money\s*laundering',
        r'fraud',
        r'scam',
        r'illegal',
    ]
    
    # Countries with higher fraud risk (ISO country codes)
    HIGH_RISK_COUNTRIES = [
        'NG',  # Nigeria
        'GH',  # Ghana
        'PK',  # Pakistan
        'BD',  # Bangladesh
    ]
    
    @classmethod
    def validate_donation_amount(cls, amount, user=None):
        """Validate donation amount for suspicious patterns"""
        errors = []
        
        # Check minimum and maximum limits
        if amount < Decimal('1.00'):
            errors.append("Minimum donation amount is $1.00")
        
        if amount > Decimal('10000.00'):
            errors.append("Maximum single donation is $10,000")
        
        # Check for suspicious round numbers (potential testing)
        if user and amount in [Decimal('1.00'), Decimal('0.01'), Decimal('999999.99')]:
            # Log suspicious amount
            logger.warning(f"Suspicious donation amount ${amount} from user {user.id}")
        
        # Check for very large donations from new users
        if user and amount > Decimal('5000.00'):
            # Check if user is new (created within last 24 hours)
            if user.date_joined > timezone.now() - timedelta(hours=24):
                errors.append("Large donations from new accounts require manual review")
        
        return errors
    
    @classmethod
    def validate_donation_message(cls, message):
        """Check donation message for suspicious content"""
        if not message:
            return []
        
        errors = []
        message_lower = message.lower()
        
        # Check for suspicious patterns
        for pattern in cls.SUSPICIOUS_PATTERNS:
            if re.search(pattern, message_lower):
                errors.append("Message contains suspicious content")
                logger.warning(f"Suspicious donation message detected: {message[:100]}")
                break
        
        # Check message length
        if len(message) > 500:
            errors.append("Message is too long (maximum 500 characters)")
        
        return errors
    
    @classmethod
    def check_rate_limiting(cls, user, ip_address):
        """Check if user/IP is making too many donation attempts"""
        errors = []
        
        # Check user rate limiting
        if user:
            user_key = f"donation_attempts_user_{user.id}"
            user_attempts = cache.get(user_key, 0)
            
            if user_attempts >= 5:  # Max 5 attempts per hour
                errors.append("Too many donation attempts. Please try again later.")
                logger.warning(f"Rate limit exceeded for user {user.id}")
        
        # Check IP rate limiting
        if ip_address:
            ip_key = f"donation_attempts_ip_{ip_address}"
            ip_attempts = cache.get(ip_key, 0)
            
            if ip_attempts >= 10:  # Max 10 attempts per hour per IP
                errors.append("Too many donation attempts from this IP. Please try again later.")
                logger.warning(f"Rate limit exceeded for IP {ip_address}")
        
        return errors
    
    @classmethod
    def increment_rate_limit_counters(cls, user, ip_address):
        """Increment rate limiting counters"""
        if user:
            user_key = f"donation_attempts_user_{user.id}"
            cache.set(user_key, cache.get(user_key, 0) + 1, 3600)  # 1 hour
        
        if ip_address:
            ip_key = f"donation_attempts_ip_{ip_address}"
            cache.set(ip_key, cache.get(ip_key, 0) + 1, 3600)  # 1 hour
    
    @classmethod
    def validate_payment_method(cls, payment_method, amount):
        """Validate payment method selection"""
        errors = []
        
        # Check if payment method is supported
        valid_methods = ['paypal', 'stripe', 'mobile_money', 'bank_transfer', 'crypto']
        if payment_method not in valid_methods:
            errors.append("Invalid payment method selected")
        
        # Some payment methods have amount restrictions
        if payment_method == 'mobile_money' and amount > Decimal('1000.00'):
            errors.append("Mobile money payments are limited to $1,000")
        
        if payment_method == 'crypto' and amount < Decimal('10.00'):
            errors.append("Cryptocurrency payments have a minimum of $10")
        
        return errors
    
    @classmethod
    def detect_fraud_patterns(cls, donation_data):
        """Detect potential fraud patterns"""
        risk_score = 0
        flags = []
        
        # Check for rapid successive donations
        if donation_data.get('user'):
            recent_donations = cache.get(f"recent_donations_{donation_data['user'].id}", [])
            if len(recent_donations) >= 3:  # 3 donations in short time
                risk_score += 30
                flags.append("Multiple rapid donations")
        
        # Check for suspicious email patterns
        if donation_data.get('donor_email'):
            email = donation_data['donor_email'].lower()
            suspicious_domains = ['tempmail.com', '10minutemail.com', 'guerrillamail.com']
            if any(domain in email for domain in suspicious_domains):
                risk_score += 20
                flags.append("Temporary email address")
        
        # Check for VPN/Proxy usage (simplified check)
        if donation_data.get('ip_address'):
            # This would typically integrate with a service like MaxMind
            # For now, just a placeholder
            pass
        
        # Check donation amount patterns
        amount = donation_data.get('amount', 0)
        if amount in [Decimal('1.00'), Decimal('0.01')]:
            risk_score += 10
            flags.append("Test amount detected")
        
        return {
            'risk_score': risk_score,
            'flags': flags,
            'requires_review': risk_score >= 50
        }

class PaymentSecurityMiddleware:
    """Middleware for payment security"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Security checks for payment-related requests
        if self._is_payment_request(request):
            # Check for suspicious headers
            if self._has_suspicious_headers(request):
                logger.warning(f"Suspicious headers detected from IP {self._get_client_ip(request)}")
                return HttpResponseForbidden("Request blocked for security reasons")
            
            # Add security headers to request
            request.security_validated = True
        
        response = self.get_response(request)
        
        # Add security headers to payment responses
        if self._is_payment_request(request):
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
            response['X-XSS-Protection'] = '1; mode=block'
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        return response
    
    def _is_payment_request(self, request):
        """Check if request is payment-related"""
        payment_paths = [
            '/donations/',
            '/webhooks/',
            '/campaigns/',
        ]
        return any(request.path.startswith(path) for path in payment_paths)
    
    def _has_suspicious_headers(self, request):
        """Check for suspicious request headers"""
        # Check for missing or suspicious User-Agent
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if not user_agent or len(user_agent) < 10:
            return True
        
        # Check for suspicious referers
        referer = request.META.get('HTTP_REFERER', '')
        if referer and 'localhost' not in referer and settings.DEBUG is False:
            # In production, check if referer is from allowed domains
            pass
        
        return False
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class WebhookSecurityValidator:
    """Security validation for webhook endpoints"""
    
    @staticmethod
    def validate_stripe_webhook(payload, signature, secret):
        """Validate Stripe webhook signature"""
        try:
            import stripe
            stripe.Webhook.construct_event(payload, signature, secret)
            return True
        except (ValueError, stripe.error.SignatureVerificationError):
            return False
    
    @staticmethod
    def validate_paypal_webhook(payload, headers):
        """Validate PayPal webhook (simplified)"""
        # In a real implementation, you would verify PayPal's signature
        # This is a simplified version
        required_headers = ['HTTP_PAYPAL_TRANSMISSION_ID', 'HTTP_PAYPAL_CERT_ID']
        return all(header in headers for header in required_headers)
    
    @staticmethod
    def log_webhook_attempt(source, ip_address, success=True):
        """Log webhook attempts for monitoring"""
        status = "SUCCESS" if success else "FAILED"
        logger.info(f"Webhook attempt from {source} at IP {ip_address}: {status}")
        
        # Track failed attempts
        if not success:
            cache_key = f"failed_webhook_{source}_{ip_address}"
            failed_count = cache.get(cache_key, 0) + 1
            cache.set(cache_key, failed_count, 3600)  # 1 hour
            
            if failed_count >= 5:
                logger.warning(f"Multiple failed webhook attempts from {source} at {ip_address}")

class DonationValidator:
    """Comprehensive donation validation"""
    
    @classmethod
    def validate_donation_request(cls, request, form_data):
        """Validate entire donation request"""
        errors = []
        warnings = []
        
        # Get request metadata
        ip_address = cls._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Basic form validation
        amount = form_data.get('amount')
        if amount:
            amount_errors = PaymentSecurityValidator.validate_donation_amount(
                amount, request.user if request.user.is_authenticated else None
            )
            errors.extend(amount_errors)
        
        # Message validation
        message = form_data.get('message', '')
        message_errors = PaymentSecurityValidator.validate_donation_message(message)
        errors.extend(message_errors)
        
        # Rate limiting
        if request.user.is_authenticated:
            rate_errors = PaymentSecurityValidator.check_rate_limiting(
                request.user, ip_address
            )
            errors.extend(rate_errors)
        
        # Payment method validation
        payment_method = form_data.get('payment_method')
        if payment_method and amount:
            method_errors = PaymentSecurityValidator.validate_payment_method(
                payment_method, amount
            )
            errors.extend(method_errors)
        
        # Fraud detection
        fraud_analysis = PaymentSecurityValidator.detect_fraud_patterns({
            'user': request.user if request.user.is_authenticated else None,
            'amount': amount,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'donor_email': form_data.get('donor_email', ''),
        })
        
        if fraud_analysis['requires_review']:
            warnings.append("Donation flagged for manual review")
        
        # Increment rate limiting counters if validation passes
        if not errors:
            PaymentSecurityValidator.increment_rate_limit_counters(
                request.user if request.user.is_authenticated else None,
                ip_address
            )
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'fraud_analysis': fraud_analysis,
            'metadata': {
                'ip_address': ip_address,
                'user_agent': user_agent,
            }
        }
    
    @staticmethod
    def _get_client_ip(request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class PaymentEncryption:
    """Utility class for payment data encryption"""
    
    @staticmethod
    def encrypt_sensitive_data(data, key=None):
        """Encrypt sensitive payment data"""
        if not key:
            key = settings.SECRET_KEY[:32].encode()  # Use first 32 chars of secret key
        
        try:
            from cryptography.fernet import Fernet
            import base64
            
            # Generate key from secret
            key = base64.urlsafe_b64encode(key)
            f = Fernet(key)
            
            # Encrypt data
            encrypted_data = f.encrypt(str(data).encode())
            return encrypted_data.decode()
            
        except ImportError:
            logger.warning("Cryptography library not available, using base64 encoding")
            import base64
            return base64.b64encode(str(data).encode()).decode()
    
    @staticmethod
    def decrypt_sensitive_data(encrypted_data, key=None):
        """Decrypt sensitive payment data"""
        if not key:
            key = settings.SECRET_KEY[:32].encode()
        
        try:
            from cryptography.fernet import Fernet
            import base64
            
            # Generate key from secret
            key = base64.urlsafe_b64encode(key)
            f = Fernet(key)
            
            # Decrypt data
            decrypted_data = f.decrypt(encrypted_data.encode())
            return decrypted_data.decode()
            
        except ImportError:
            logger.warning("Cryptography library not available, using base64 decoding")
            import base64
            return base64.b64decode(encrypted_data.encode()).decode()
