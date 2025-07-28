from django.urls import path
from . import views

# Remove app_name to avoid namespace issues with simple URL reversing
urlpatterns = [
    path('', views.signup_view, name='signup'),  # This creates the 'signup' URL name
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile_view, name='edit_profile'),
]
