from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from .views import CustomLoginView  # Import the CustomLoginView

urlpatterns = [
    path('', views.home, name='home'),
    
    # Employee routes - use CustomLoginView with employee template
    path('employee/login/', CustomLoginView.as_view(template_name='hr_app/employee_login.html'), name='employee_login'),
    path('employee/dashboard/', views.employee_dashboard, name='employee_dashboard'),
    
    # HR Admin routes - use CustomLoginView with HR template  
    path('hr/login/', CustomLoginView.as_view(template_name='hr_app/hr_login.html'), name='hr_login'),
    path('hr/dashboard/', views.hr_dashboard, name='hr_dashboard'),
    
    # Common routes
    path('apply-leave/', views.apply_leave, name='apply_leave'),
    path('payslips/', views.view_payslips, name='view_payslips'),
    path('candidate-registration/', views.candidate_registration, name='candidate_registration'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # Fallback for default Django redirect
    path('accounts/profile/', views.employee_dashboard, name='profile_redirect'),
]