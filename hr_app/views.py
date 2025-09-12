from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login as auth_login
from .models import Employee, LeaveRequest, Payroll, Candidate, Department
from .forms import LeaveRequestForm, CandidateForm
from django.contrib.auth.views import LoginView

# Add this class - it's the simplest fix
class CustomLoginView(LoginView):
    def get_success_url(self):
        # Check if user is staff/HR, redirect to appropriate dashboard
        if self.request.user.is_staff or self.request.user.is_superuser:
            return '/hr/dashboard/'
        else:
            return '/employee/dashboard/'

# Check if user is HR staff
def is_hr_staff(user):
    return user.is_staff or user.is_superuser

def home(request):
    return render(request, 'hr_app/home.html')

# Employee Dashboard
@login_required
def employee_dashboard(request):
    try:
        employee = Employee.objects.get(user=request.user)
        leave_requests = LeaveRequest.objects.filter(employee=employee)
        payrolls = Payroll.objects.filter(employee=employee)
        
        context = {
            'employee': employee,
            'leave_requests': leave_requests,
            'payrolls': payrolls,
        }
        return render(request, 'hr_app/employee_dashboard.html', context)
    except Employee.DoesNotExist:
        return render(request, 'hr_app/employee_dashboard.html')

# HR Admin Dashboard
@login_required
@user_passes_test(is_hr_staff)
def hr_dashboard(request):
    total_employees = Employee.objects.count()
    pending_leaves = LeaveRequest.objects.filter(status='Pending').count()
    total_departments = Department.objects.count()
    
    context = {
        'total_employees': total_employees,
        'pending_leaves': pending_leaves,
        'total_departments': total_departments,
    }
    return render(request, 'hr_app/hr_dashboard.html', context)

# Leave Application
@login_required
def apply_leave(request):
    if request.method == 'POST':
        form = LeaveRequestForm(request.POST)
        if form.is_valid():
            leave_request = form.save(commit=False)
            leave_request.employee = Employee.objects.get(user=request.user)
            leave_request.save()
            return redirect('employee_dashboard')
    else:
        form = LeaveRequestForm()
    
    return render(request, 'hr_app/apply_leave.html', {'form': form})

# Payslips View - THIS WAS MISSING!
@login_required
def view_payslips(request):
    try:
        employee = Employee.objects.get(user=request.user)
        payrolls = Payroll.objects.filter(employee=employee)
        return render(request, 'hr_app/payslips.html', {'payrolls': payrolls})
    except Employee.DoesNotExist:
        return render(request, 'hr_app/payslips.html', {'payrolls': []})

# Candidate Registration
def candidate_registration(request):
    if request.method == 'POST':
        form = CandidateForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('home')
    else:
        form = CandidateForm()
    
    return render(request, 'hr_app/candidate_registration.html', {'form': form})