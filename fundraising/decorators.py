from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponseForbidden

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
