from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponseForbidden
from functools import wraps
import logging
from .security import DonationValidator

logger = logging.getLogger(__name__)

def role_required(role):
    """
    Decorator for views that checks that the user has a specific role,
    redirecting to the log-in page if necessary.
    """
    def check_role(user):
        return user.is_authenticated and user.role == role
    return user_passes_test(check_role)

def student_required(function=None):
    """
    Decorator for views that checks that the logged-in user is a student.
    """
    actual_decorator = role_required('student')
    if function:
        return actual_decorator(function)
    return actual_decorator

def donor_required(function=None):
    """
    Decorator for views that checks that the logged-in user is a donor.
    """
    actual_decorator = role_required('donor')
    if function:
        return actual_decorator(function)
    return actual_decorator

def admin_required(function=None):
    """
    Decorator for views that checks that the logged-in user is an admin.
    """
    actual_decorator = role_required('admin')
    if function:
        return actual_decorator(function)
    return actual_decorator

def secure_payment_view(view_func):
    """
    Decorator that adds security validation to payment-related views
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Only apply security validation to POST requests
        if request.method == 'POST':
            # Validate the donation request
            form_data = {
                'amount': request.POST.get('amount'),
                'payment_method': request.POST.get('payment_method'),
                'message': request.POST.get('message', ''),
                'donor_email': request.POST.get('donor_email', ''),
            }
            
            validation_result = DonationValidator.validate_donation_request(request, form_data)
            
            # If validation fails, return forbidden response
            if not validation_result['valid']:
                logger.warning(f"Payment security validation failed: {validation_result['errors']}")
                return HttpResponseForbidden("Request blocked for security reasons")
            
            # Attach validation result to request for use in view
            request.security_validation = validation_result
        
        return view_func(request, *args, **kwargs)
    
    return wrapper

def log_payment_activity(activity_type):
    """
    Decorator that logs payment-related activities for monitoring
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get client IP
            ip_address = request.META.get('HTTP_X_FORWARDED_FOR')
            if ip_address:
                ip_address = ip_address.split(',')[0]
            else:
                ip_address = request.META.get('REMOTE_ADDR', 'unknown')
            
            # Log the activity
            user_id = request.user.id if request.user.is_authenticated else 'anonymous'
            logger.info(f"Payment activity: {activity_type} from user {user_id} at IP {ip_address}")
            
            try:
                response = view_func(request, *args, **kwargs)
                
                # Log successful completion
                logger.info(f"Payment activity completed: {activity_type} from user {user_id}")
                
                return response
                
            except Exception as e:
                # Log any errors
                logger.error(f"Payment activity failed: {activity_type} from user {user_id} - Error: {str(e)}")
                raise
        
        return wrapper
    return decorator

def rate_limit_payment(max_attempts=5, window_minutes=60):
    """
    Decorator that implements rate limiting for payment attempts
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from django.core.cache import cache
            from django.http import HttpResponseTooManyRequests
            
            # Get client identifier
            if request.user.is_authenticated:
                client_id = f"user_{request.user.id}"
            else:
                ip_address = request.META.get('HTTP_X_FORWARDED_FOR')
                if ip_address:
                    ip_address = ip_address.split(',')[0]
                else:
                    ip_address = request.META.get('REMOTE_ADDR', 'unknown')
                client_id = f"ip_{ip_address}"
            
            # Check rate limit
            cache_key = f"payment_rate_limit_{client_id}"
            attempts = cache.get(cache_key, 0)
            
            if attempts >= max_attempts:
                logger.warning(f"Rate limit exceeded for {client_id}")
                return HttpResponseTooManyRequests("Too many payment attempts. Please try again later.")
            
            # Increment counter
            cache.set(cache_key, attempts + 1, window_minutes * 60)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator

def require_https_in_production(view_func):
    """
    Decorator that requires HTTPS for payment views in production
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from django.conf import settings
        from django.http import HttpResponsePermanentRedirect
        
        # Only enforce HTTPS in production
        if not settings.DEBUG and not request.is_secure():
            logger.warning(f"Insecure payment request from {request.META.get('REMOTE_ADDR', 'unknown')}")
            return HttpResponsePermanentRedirect(
                'https://' + request.get_host() + request.get_full_path()
            )
        
        return view_func(request, *args, **kwargs)
    
    return wrapper
