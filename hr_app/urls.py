from django.urls import path
from . import views
from .views import CustomLoginView

urlpatterns = [
    path('', views.home, name='home'),
    
    # Employee routes
    path('employee/login/', CustomLoginView.as_view(template_name='hr_app/employee_login.html'), name='employee_login'),
    path('employee/dashboard/', views.employee_dashboard, name='employee_dashboard'),
    path('leave-history/', views.leave_history, name='leave_history'),
    path('apply-leave/', views.apply_leave, name='apply_leave'),
    path('payslips/', views.view_payslips, name='view_payslips'),
    path('payslip-pdf/<int:payroll_id>/', views.generate_payslip_pdf, name='generate_payslip_pdf'),
    
    # HR Admin routes  
    path('hr/login/', CustomLoginView.as_view(template_name='hr_app/hr_login.html'), name='hr_login'),
    path('hr/dashboard/', views.hr_dashboard, name='hr_dashboard'),
    path('hr/manage-leaves/', views.manage_leaves, name='manage_leaves'),
    path('hr/approve-leave/<int:leave_id>/', views.approve_leave, name='approve_leave'),
    path('hr/reject-leave/<int:leave_id>/', views.reject_leave, name='reject_leave'),
    path('hr/candidates/', views.candidate_list, name='candidate_list'),
    
    # Common routes
    path('candidate-registration/', views.candidate_registration, name='candidate_registration'),
    path('logout/', views.custom_logout, name='logout'),
    
    # Fallback for default Django redirect
    path('accounts/profile/', views.employee_dashboard, name='profile_redirect'),
]