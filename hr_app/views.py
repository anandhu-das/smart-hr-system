from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login as auth_login, logout
from django.contrib import messages
from django.http import HttpResponse, FileResponse
from django.contrib.auth.views import LoginView
from django.db.models import Sum, Avg
from django.contrib.auth.models import User
from datetime import datetime
import io

# PDF tools
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors

# Models + Forms
from .models import Employee, LeaveRequest, Payroll, Candidate, Department, PerformanceReview
from .forms import LeaveRequestForm, CandidateForm, PayrollForm, PayrollCalculationForm, EmployeeForm
from .forms import PayrollCalculationForm
from django.db import IntegrityError
from datetime import date, timedelta
from django.db.models import Sum, F


# ---------------------------
# Permissions
# ---------------------------
def is_hr_staff(user):
    """Check if user is HR (staff, superuser, or HR dept)"""
    if user.is_staff or user.is_superuser:
        return True
    try:
        employee = Employee.objects.get(user=user)
        if employee.department and "hr" in employee.department.name.lower():
            return True
    except Employee.DoesNotExist:
        pass
    return False


# ---------------------------
# Authentication
# ---------------------------
class CustomLoginView(LoginView):
    def get_success_url(self):
        if self.request.user.is_staff or self.request.user.is_superuser or is_hr_staff(self.request.user):
            return '/hr/dashboard/'
        else:
            return '/employee/dashboard/'


@login_required
def custom_logout(request):
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('home')


def home(request):
    return render(request, 'hr_app/home.html')


# ---------------------------
# Dashboards
# ---------------------------
@login_required
def employee_dashboard(request):
    try:
        employee = Employee.objects.get(user=request.user)
        leave_requests = LeaveRequest.objects.filter(employee=employee).order_by('-applied_on')[:5]
        payrolls = Payroll.objects.filter(employee=employee).order_by('-year', '-month')[:3]
        return render(request, 'hr_app/employee_dashboard.html', {
            'employee': employee,
            'leave_requests': leave_requests,
            'payrolls': payrolls,
        })
    except Employee.DoesNotExist:
        messages.info(request, 'Please complete your employee profile.')
        return render(request, 'hr_app/employee_dashboard.html')


@login_required
@user_passes_test(is_hr_staff)
def hr_dashboard(request):
    total_employees = Employee.objects.count()
    pending_leaves = LeaveRequest.objects.filter(status='Pending').count()
    total_departments = Department.objects.count()
    recent_candidates = Candidate.objects.order_by('-applied_on')[:5]
    pending_payments = Payroll.objects.filter(paid=False).count()
    total_paid = Payroll.objects.filter(paid=True).aggregate(Sum('net_salary'))['net_salary__sum'] or 0
    return render(request, 'hr_app/hr_dashboard.html', {
        'total_employees': total_employees,
        'pending_leaves': pending_leaves,
        'total_departments': total_departments,
        'recent_candidates': recent_candidates,
        'pending_payments': pending_payments,
        'total_paid': total_paid,
    })


# ---------------------------
# Leave Management
# ---------------------------
@login_required
def apply_leave(request):
    try:
        employee = Employee.objects.get(user=request.user)
        leave_requests = LeaveRequest.objects.filter(employee=employee).order_by('-applied_on')[:5]
    except Employee.DoesNotExist:
        leave_requests = []
        messages.error(request, 'Please complete your employee profile before applying for leave.')

    if request.method == 'POST':
        form = LeaveRequestForm(request.POST)
        if form.is_valid():
            leave_request = form.save(commit=False)
            leave_request.employee = employee
            leave_request.save()
            messages.success(request, 'Leave application submitted successfully!')
            return redirect('employee_dashboard')
    else:
        form = LeaveRequestForm()
    return render(request, 'hr_app/apply_leave.html', {'form': form, 'leave_requests': leave_requests})


@login_required
def leave_history(request):
    try:
        employee = Employee.objects.get(user=request.user)
        leaves = LeaveRequest.objects.filter(employee=employee).order_by('-applied_on')
        return render(request, 'hr_app/leave_history.html', {'leaves': leaves})
    except Employee.DoesNotExist:
        messages.error(request, 'Employee profile not found.')
        return render(request, 'hr_app/leave_history.html', {'leaves': []})


@login_required
@user_passes_test(is_hr_staff)
def manage_leaves(request):
    return render(request, 'hr_app/manage_leaves.html', {
        'pending_leaves': LeaveRequest.objects.filter(status='Pending'),
        'approved_leaves': LeaveRequest.objects.filter(status='Approved')[:10],
        'rejected_leaves': LeaveRequest.objects.filter(status='Rejected')[:10],
    })


@login_required
@user_passes_test(is_hr_staff)
def approve_leave(request, leave_id):
    leave = get_object_or_404(LeaveRequest, id=leave_id)
    leave.status = 'Approved'
    leave.save()
    messages.success(request, f'Leave approved for {leave.employee}')
    return redirect('manage_leaves')


@login_required
@user_passes_test(is_hr_staff)
def reject_leave(request, leave_id):
    leave = get_object_or_404(LeaveRequest, id=leave_id)
    leave.status = 'Rejected'
    leave.save()
    messages.success(request, f'Leave rejected for {leave.employee}')
    return redirect('manage_leaves')


# ---------------------------
# Candidate Management
# ---------------------------
def candidate_registration(request):
    if request.method == 'POST':
        form = CandidateForm(request.POST, request.FILES)
        if form.is_valid():
            candidate = form.save()
            messages.success(request, f'Application submitted! Reference ID {candidate.id}')
            return redirect('home')
    else:
        form = CandidateForm()
    return render(request, 'hr_app/candidate_registration.html', {'form': form})


@login_required
@user_passes_test(is_hr_staff)
def candidate_list(request):
    candidates = Candidate.objects.all().order_by('-applied_on')
    return render(request, 'hr_app/candidate_list.html', {'candidates': candidates})


# ---------------------------
# Payroll Management
# ---------------------------
@login_required
@user_passes_test(is_hr_staff)
def payroll_dashboard(request):
    recent_payrolls = Payroll.objects.select_related('employee').order_by('-year', '-month')[:10]
    pending_payments = Payroll.objects.filter(paid=False).count()
    total_paid = Payroll.objects.filter(paid=True).aggregate(Sum('net_salary'))['net_salary__sum'] or 0
    return render(request, 'hr_app/payroll_dashboard.html', {
        'recent_payrolls': recent_payrolls,
        'pending_payments': pending_payments,
        'total_paid': total_paid,
    })

@login_required
@user_passes_test(is_hr_staff)
def generate_bulk_payroll(request):
    if request.method == 'POST':
        form = PayrollCalculationForm(request.POST)
        if form.is_valid():
            month = form.cleaned_data['month']
            year = form.cleaned_data['year']
            
            employees = Employee.objects.all()
            created_count = 0
            
            for employee in employees:
                if Payroll.objects.filter(employee=employee, month=month, year=year).exists():
                    continue

                basic_salary = employee.salary
                
                # Calculate days in the month
                days_in_month = (date(year, list(form.fields['month'].choices).index((month, month)) + 2, 1) - date(year, list(form.fields['month'].choices).index((month, month)) + 1, 1)).days

                unpaid_leaves = LeaveRequest.objects.filter(
                    employee=employee,
                    status='Approved',
                    start_date__month=date(year, list(form.fields['month'].choices).index((month, month)) + 1, 1).month,
                    start_date__year=year
                ).aggregate(total_days=Sum(F('end_date') - F('start_date'))).get('total_days', timedelta(days=0)).days

                daily_rate = basic_salary / days_in_month
                leave_deduction = unpaid_leaves * daily_rate

                try:
                    payroll = Payroll.objects.create(
                        employee=employee,
                        month=month,
                        year=year,
                        basic_salary=basic_salary,
                        house_rent_allowance=basic_salary * 0.15,
                        travel_allowance=basic_salary * 0.1,
                        other_deductions=leave_deduction
                    )
                    created_count += 1
                except IntegrityError:
                    pass
            
            messages.success(request, f'Successfully generated payroll for {created_count} employees for {month}, {year}.')
            return redirect('manage_payroll')
    else:
        form = PayrollCalculationForm()
    
    return render(request, 'hr_app/bulk_payroll.html', {'form': form})


@login_required
@user_passes_test(is_hr_staff)
def manage_payroll(request):
    payrolls = Payroll.objects.select_related('employee').all()
    return render(request, 'hr_app/manage_payroll.html', {'payrolls': payrolls})


@login_required
@user_passes_test(is_hr_staff)
def create_payroll(request, employee_id=None):
    employee = get_object_or_404(Employee, id=employee_id) if employee_id else None
    if request.method == 'POST':
        form = PayrollForm(request.POST)
        if form.is_valid():
            payroll = form.save(commit=False)
            if employee:
                payroll.employee = employee
            payroll.save()
            messages.success(request, f'Payroll created for {payroll.employee}')
            return redirect('manage_payroll')
    else:
        form = PayrollForm()
    return render(request, 'hr_app/create_payroll.html', {'form': form, 'employee': employee})


@login_required
@user_passes_test(is_hr_staff)
def edit_payroll(request, payroll_id):
    payroll = get_object_or_404(Payroll, id=payroll_id)
    if request.method == 'POST':
        form = PayrollForm(request.POST, instance=payroll)
        if form.is_valid():
            form.save()
            messages.success(request, 'Payroll updated')
            return redirect('manage_payroll')
    else:
        form = PayrollForm(instance=payroll)
    return render(request, 'hr_app/edit_payroll.html', {'form': form})


@login_required
@user_passes_test(is_hr_staff)
def delete_payroll(request, payroll_id):
    payroll = get_object_or_404(Payroll, id=payroll_id)
    if request.method == 'POST':
        payroll.delete()
        messages.success(request, 'Payroll deleted')
        return redirect('manage_payroll')
    return render(request, 'hr_app/delete_payroll.html', {'payroll': payroll})

# hr_app/views.py

# ... (keep all your existing code) ...

# ---------------------------
# Payroll Management (Additional)
# ---------------------------
@login_required
def view_payslips(request):
    """
    Allows an employee to view their list of payslips.
    """
    try:
        employee = Employee.objects.get(user=request.user)
        payrolls = Payroll.objects.filter(employee=employee).order_by('-year', '-month')
        return render(request, 'hr_app/view_payslips.html', {'payrolls': payrolls})
    except Employee.DoesNotExist:
        messages.error(request, 'Employee profile not found.')
        return render(request, 'hr_app/view_payslips.html', {'payrolls': []})

@login_required
def generate_payslip_pdf(request, payroll_id):
    """
    Generates a PDF payslip for a specific payroll record.
    """
    payroll = get_object_or_404(Payroll, id=payroll_id, employee__user=request.user)

    # Create a file-like buffer for the PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()

    # Add content to the story
    title = Paragraph(f"<b>Payslip for {payroll.employee.user.get_full_name()}</b>", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))

    # Basic Info
    info_data = [
        ["Employee ID:", payroll.employee.employee_id],
        ["Month/Year:", f"{payroll.month}, {payroll.year}"],
        ["Position:", payroll.employee.position],
    ]
    info_table = Table(info_data)
    story.append(info_table)
    story.append(Spacer(1, 12))

    # Earnings and Deductions Table
    earnings_data = [
        ['Earnings', 'Amount (₹)'],
        ['Basic Salary', payroll.basic_salary],
        ['House Rent Allowance', payroll.house_rent_allowance],
        ['Travel Allowance', payroll.travel_allowance],
        ['Medical Allowance', payroll.medical_allowance],
        ['Special Allowance', payroll.special_allowance],
    ]

    deductions_data = [
        ['Deductions', 'Amount (₹)'],
        ['Professional Tax', payroll.professional_tax],
        ['Income Tax', payroll.income_tax],
        ['Other Deductions', payroll.other_deductions],
        ['Employee PF', payroll.calculate_epf()[0]],
    ]

    # Add a total earnings/deductions row at the end
    total_earnings = payroll.calculate_total_earnings()
    total_deductions = payroll.calculate_total_deductions()
    earnings_data.append(['<b>Total Earnings</b>', f'<b>{total_earnings}</b>'])
    deductions_data.append(['<b>Total Deductions</b>', f'<b>{total_deductions}</b>'])

    earnings_table = Table(earnings_data, colWidths=[3*inch, 2*inch])
    deductions_table = Table(deductions_data, colWidths=[3*inch, 2*inch])

    table_style = TableStyle([('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                             ('GRID', (0,0), (-1,-1), 1, colors.black),
                             ('BOX', (0,0), (-1,-1), 1, colors.black),
                             ('ALIGN', (1,0), (-1,-1), 'RIGHT')])

    earnings_table.setStyle(table_style)
    deductions_table.setStyle(table_style)

    story.append(earnings_table)
    story.append(Spacer(1, 24))
    story.append(deductions_table)
    story.append(Spacer(1, 24))

    # Net Salary
    story.append(Paragraph(f"<b>Net Salary: ₹{payroll.net_salary}</b>", styles['Heading2']))

    # Build the PDF
    doc.build(story)
    buffer.seek(0)

    # Return the PDF as an HTTP response
    return FileResponse(buffer, as_attachment=True, filename=f"payslip_{payroll.employee.employee_id}_{payroll.month}_{payroll.year}.pdf")


# ---------------------------
# Employee Management (NEW)
# ---------------------------
@login_required
@user_passes_test(is_hr_staff)
def manage_employees(request):
    employees = Employee.objects.select_related("user", "department").all()
    return render(request, "hr_app/manage_employees.html", {"employees": employees})


@login_required
@user_passes_test(is_hr_staff)
def add_employee(request):
    if request.method == "POST":
        form = EmployeeForm(request.POST)
        if form.is_valid():
            employee = form.save(commit=False)
            # link employee to a user (basic)
            user = User.objects.create_user(
                username=employee.employee_id,
                password="password123",  # you can improve later
                first_name=employee.employee_id
            )
            employee.user = user
            employee.save()
            messages.success(request, "Employee added successfully")
            return redirect("manage_employees")
    else:
        form = EmployeeForm()
    return render(request, "hr_app/add_employee.html", {"form": form})


@login_required
@user_passes_test(is_hr_staff)
def edit_employee(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    if request.method == "POST":
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, "Employee updated successfully")
            return redirect("manage_employees")
    else:
        form = EmployeeForm(instance=employee)
    return render(request, "hr_app/edit_employee.html", {"form": form, "employee": employee})


@login_required
@user_passes_test(is_hr_staff)
def delete_employee(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    if request.method == "POST":
        employee.delete()
        messages.success(request, "Employee deleted")
        return redirect("manage_employees")
    return render(request, "hr_app/delete_employee.html", {"employee": employee})


@login_required
def my_profile(request):
    try:
        employee = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        employee = None
    return render(request, "hr_app/my_profile.html", {"employee": employee})

@login_required
@user_passes_test(is_hr_staff)
def promotion_tracker(request):
    # Example criteria: > 2 years tenure and average rating > 4
    eligible_employees = []
    today = datetime.now().date()
    
    for employee in Employee.objects.all():
        years_of_service = (today - employee.date_joined).days / 365.25
        
        if years_of_service >= 2:
            avg_rating = PerformanceReview.objects.filter(employee=employee).aggregate(Avg('rating'))['rating__avg']
            
            if avg_rating and avg_rating > 4:
                eligible_employees.append({
                    'employee': employee,
                    'years_of_service': round(years_of_service, 2),
                    'average_rating': round(avg_rating, 2)
                })

    return render(request, 'hr_app/promotion_tracker.html', {'eligible_employees': eligible_employees})
