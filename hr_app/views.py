from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login as auth_login, logout
from django.contrib import messages
from django.http import HttpResponse, FileResponse
from django.contrib.auth.views import LoginView
# Consolidated imports for calculations
from django.db.models import Sum, Avg, F
from django.contrib.auth.models import User
from datetime import datetime, date, timedelta
from decimal import Decimal # CRITICAL FIX: Import Decimal for calculations
import calendar # CRITICAL FIX: Import calendar for accurate days in month
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
# CRITICAL FIX: Add MONTH_CHOICES to the import list
from .forms import LeaveRequestForm, CandidateForm, PayrollForm, PayrollCalculationForm, EmployeeForm, MONTH_CHOICES
from django.db import IntegrityError


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
# ---------------------------
# Leave Management
# ---------------------------
@login_required
def apply_leave(request):
    # CRITICAL FIX 1: Retrieve the employee object once, and set a default
    # to avoid the UnboundLocalError later.
    employee = None
    try:
        employee = Employee.objects.get(user=request.user)
        leave_requests = LeaveRequest.objects.filter(employee=employee).order_by('-applied_on')[:5]
    except Employee.DoesNotExist:
        leave_requests = []
        messages.error(request, 'Please complete your employee profile before applying for leave.')
        # The 'employee' variable is now safely set to None if the profile doesn't exist.

    if request.method == 'POST':
        # CRITICAL FIX 2: Check if the profile exists before processing the form.
        if employee is None:
            # If the profile doesn't exist, we prevent form submission and redirect.
            messages.error(request, 'Cannot submit leave: Employee profile not found.')
            return redirect('apply_leave') 
        
        form = LeaveRequestForm(request.POST)
        if form.is_valid():
            leave_request = form.save(commit=False)
            leave_request.employee = employee # This line is now safe
            leave_request.save()
            messages.success(request, 'Leave application submitted successfully!')
            return redirect('employee_dashboard')
    else:
        form = LeaveRequestForm()
        
    return render(request, 'hr_app/apply_leave.html', {'form': form, 'leave_requests': leave_requests})


@login_required
def leave_history(request):
    """Retrieves all leave requests for the currently logged-in employee."""
    employee = None
    try:
        employee = Employee.objects.get(user=request.user)
        # Fetch all leaves, ordered by most recently applied
        leaves = LeaveRequest.objects.filter(employee=employee).order_by('-applied_on')
        return render(request, 'hr_app/leave_history.html', {'leaves': leaves})
    except Employee.DoesNotExist:
        messages.error(request, 'Employee profile not found. Cannot view history.')
        # Return an empty list if the profile doesn't exist
        return render(request, 'hr_app/leave_history.html', {'leaves': []})


# hr_app/views.py

@login_required
@user_passes_test(is_hr_staff)
def manage_leaves(request):
    """View to show all pending, approved, and rejected leave requests for HR staff."""
    
    pending_leaves = LeaveRequest.objects.filter(status='Pending').order_by('applied_on')
    
    # Fetch recent approved/rejected leaves (showing top 10 of each)
    approved_leaves = LeaveRequest.objects.filter(status='Approved').order_by('-applied_on')[:10]
    rejected_leaves = LeaveRequest.objects.filter(status='Rejected').order_by('-applied_on')[:10]
    
    context = {
        'pending_leaves': pending_leaves,
        'approved_leaves': approved_leaves,
        'rejected_leaves': rejected_leaves,
    }
    return render(request, 'hr_app/manage_leaves.html', context)


@login_required
@user_passes_test(is_hr_staff)
def approve_leave(request, leave_id):
    """Allows HR staff to approve a leave request."""
    leave = get_object_or_404(LeaveRequest, id=leave_id)
    
    # CRITICAL SECURITY CHECK: Prevent self-approval 
    try:
        current_employee = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        current_employee = None
        
    if current_employee and leave.employee == current_employee:
        messages.error(request, f"You cannot approve your own leave request for {leave.employee.user.username}.")
        return redirect('manage_leaves')

    if leave.status != 'Approved':
        leave.status = 'Approved'
        leave.save()
        messages.success(request, f"Leave request for {leave.employee.user.username} approved.")
    else:
        messages.info(request, "Leave request is already approved.")
        
    return redirect('manage_leaves')


@login_required
@user_passes_test(is_hr_staff)
def reject_leave(request, leave_id):
    """Allows HR staff to reject a leave request."""
    leave = get_object_or_404(LeaveRequest, id=leave_id)
    
    # CRITICAL SECURITY CHECK: Prevent self-rejection
    try:
        current_employee = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        current_employee = None
        
    if current_employee and leave.employee == current_employee:
        messages.error(request, f"You cannot reject your own leave request for {leave.employee.user.username}.")
        return redirect('manage_leaves')
        
    if leave.status != 'Rejected':
        leave.status = 'Rejected'
        leave.save()
        # Using warning for a negative action like rejection
        messages.warning(request, f"Leave request for {leave.employee.user.username} rejected.")
    else:
        messages.info(request, "Leave request is already rejected.")
        
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
    # Ensure Decimal is available within the function scope
    from decimal import Decimal 
    import calendar 
    
    if request.method == 'POST':
        form = PayrollCalculationForm(request.POST)
        if form.is_valid():
            month = form.cleaned_data['month']
            year = form.cleaned_data['year']
            
            employees = Employee.objects.all()
            created_count = 0
            
            # Get month number (1-12) for calculations
            month_num = list(form.fields['month'].choices).index((month, month)) + 1
            
            # Get total days in the month
            days_in_month = calendar.monthrange(year, month_num)[1]

            for employee in employees:
                if Payroll.objects.filter(employee=employee, month=month, year=year).exists():
                    continue

                basic_salary = employee.salary
                
                # Calculate unpaid leaves for deduction
                leave_aggregate = LeaveRequest.objects.filter(
                    employee=employee,
                    status='Approved',
                    start_date__month=month_num,
                    start_date__year=year
                ).aggregate(total_days=Sum(F('end_date') - F('start_date')))
                
                # --- FIX: Safely extract days from timedelta ---
                total_leave_duration = leave_aggregate.get('total_days')
                
                # If total_days is None (no approved leaves found), set leave_days to 0
                if total_leave_duration is None:
                    leave_days = 0
                else:
                    leave_days = total_leave_duration.days
                
                unpaid_leaves = leave_days
                
                # Ensure division/multiplication involves only Decimals
                if days_in_month == 0:
                    daily_rate = Decimal('0')
                else:
                    daily_rate = basic_salary / Decimal(days_in_month) 

                leave_deduction = daily_rate * Decimal(unpaid_leaves)
                
                # --- Convert percentage floats to Decimal objects ---
                house_rent_allowance = basic_salary * Decimal('0.15')
                travel_allowance = basic_salary * Decimal('0.10')

                try:
                    payroll = Payroll.objects.create(
                        employee=employee,
                        month=month,
                        year=year,
                        basic_salary=basic_salary,
                        house_rent_allowance=house_rent_allowance,
                        travel_allowance=travel_allowance,
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

    # Get filter parameters from the request's GET data
    month = request.GET.get('month')
    year = request.GET.get('year')
    status = request.GET.get('status') 

    # Apply filters dynamically
    if month:
        payrolls = payrolls.filter(month=month)
    
    if year and year.isdigit():
        payrolls = payrolls.filter(year=int(year))
        
    if status == 'paid':
        payrolls = payrolls.filter(paid=True)
    elif status == 'pending':
        payrolls = payrolls.filter(paid=False)

    # --- Data for Dropdowns ---
    # Get all unique years from existing payrolls
    years = Payroll.objects.order_by('-year').values_list('year', flat=True).distinct()
    
    # FIX: Use the directly imported constant for months
    months = [m[0] for m in MONTH_CHOICES] 

    return render(request, 'hr_app/manage_payroll.html', {
        'payrolls': payrolls,
        'months': months,
        'years': years,
        # Pass back the current selections to keep the dropdowns active after filtering
        'selected_month': month,
        'selected_year': year,
        'selected_status': status,
    })


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
    # CRITICAL FIX: Ensure is_hr_staff is checked first, and if true,
    # simply retrieve the payroll object by ID.
    
    if is_hr_staff(request.user):
        # HR staff can view ANY payroll by its ID.
        # This will return the payroll or raise the 404 error if ID doesn't exist.
        payroll = get_object_or_404(Payroll, id=payroll_id)
    else:
        # Regular employee can ONLY view their own payroll.
        payroll = get_object_or_404(Payroll, id=payroll_id, employee__user=request.user)

    # Ensure Decimal is imported for proper calculation
    from decimal import Decimal 
    
    # Create a file-like buffer for the PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()

    # CRITICAL: If the system cannot find the payroll object (e.g., if it was deleted)
    # The get_object_or_404 already handles the 404, so we proceed with PDF generation.

    # Earnings and Deductions Table preparation
    employee_pf, employer_pf = payroll.calculate_epf()
    
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
        ['Employee PF', employee_pf],
    ]

    # Add a total earnings/deductions row at the end
    total_earnings = payroll.calculate_total_earnings()
    total_deductions = payroll.calculate_total_deductions()
    earnings_data.append(['<b>Total Earnings</b>', f'<b>{total_earnings}</b>'])
    deductions_data.append(['<b>Total Deductions</b>', f'<b>{total_deductions}</b>'])

    # --- PDF Content Assembly ---
    # (Rest of PDF generation code from your previous version)
    
    # Add content to the story
    title = Paragraph(f"<b>Payslip for {payroll.employee.user.get_full_name()}</b>", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))

    # Basic Info Table
    info_data = [
        ["Employee ID:", payroll.employee.employee_id],
        ["Month/Year:", f"{payroll.month}, {payroll.year}"],
        ["Position:", payroll.employee.position],
    ]
    info_table = Table(info_data)
    story.append(info_table)
    story.append(Spacer(1, 12))

    # Earnings/Deductions Tables
    table_style = TableStyle([('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                             ('GRID', (0,0), (-1,-1), 1, colors.black),
                             ('BOX', (0,0), (-1,-1), 1, colors.black),
                             ('ALIGN', (1,0), (-1,-1), 'RIGHT')])

    earnings_table = Table(earnings_data, colWidths=[3*inch, 2*inch])
    deductions_table = Table(deductions_data, colWidths=[3*inch, 2*inch])
    earnings_table.setStyle(table_style)
    deductions_table.setStyle(table_style)

    story.append(earnings_table)
    story.append(Spacer(1, 24))
    story.append(deductions_table)
    story.append(Spacer(1, 24))

    # Net Salary
    story.append(Paragraph(f"<b>Net Salary: ₹{payroll.net_salary}</b>", styles['Heading2']))

    # Build and return
    doc.build(story)
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"payslip_{payroll.employee.employee_id}_{payroll.month}_{payroll.year}.pdf")

# ---------------------------
# Employee Management
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
                password="password123",
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


# ---------------------------
# Promotion Tracker
# ---------------------------
# hr_app/views.py

# hr_app/views.py

@login_required
@user_passes_test(is_hr_staff)
def promotion_tracker(request):
    """
    Calculates score for ALL employees (who meet min tenure) for transparency.
    """
    from decimal import Decimal
    from datetime import timedelta
    from django.db.models import Sum, F
    
    all_employees_with_score = []
    today = datetime.now().date()
    
    for employee in Employee.objects.all():
        years_of_service = (today - employee.date_joined).days / 365.25
        
        # Only skip if they fail the MANDATORY MINIMUM 2-year tenure check.
        if years_of_service < 2:
            continue

        # --- CALCULATE OBJECTIVE SCORE ---
        # (The scoring logic remains the same as before)
        tenure_score = min(Decimal(years_of_service) * Decimal('10'), Decimal('40'))
        
        one_year_ago = today - timedelta(days=365)
        leave_duration = LeaveRequest.objects.filter(
            employee=employee,
            status='Approved',
            start_date__gte=one_year_ago 
        ).aggregate(total_days=Sum(F('end_date') - F('start_date')))['total_days']
        
        total_leave_days = leave_duration.days if leave_duration else 0
        
        attendance_deduction = Decimal(total_leave_days) / Decimal('2') * Decimal('5')
        attendance_score = max(Decimal('30') - attendance_deduction, Decimal('0'))
        
        base_performance_score = Decimal('30') 
        total_score = tenure_score + attendance_score + base_performance_score
        
        # Add ALL employees who passed the minimum 2-year check
        all_employees_with_score.append({
            'employee': employee,
            'tenure': round(years_of_service, 2),
            'score': round(total_score, 2),
            'attendance_days': total_leave_days,
            'is_eligible': total_score >= Decimal('75') # New flag to check eligibility
        })

    return render(request, 'hr_app/promotion_tracker.html', {'eligible_employees': all_employees_with_score})

@login_required
def edit_my_profile(request):
    """Allows an employee to edit their own profile details."""
    try:
        # CRITICAL: Retrieve the employee profile linked to the currently logged-in user
        employee = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        messages.error(request, "Error: Employee profile not found.")
        return redirect('my_profile') # Redirect back if profile is missing

    if request.method == "POST":
        # Pass the instance to the form to update the existing record
        form = EmployeeForm(request.POST, instance=employee) 
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("my_profile")
    else:
        # Load the form with the employee's existing data
        form = EmployeeForm(instance=employee)
        
    return render(request, "hr_app/edit_my_profile.html", {"form": form, "employee": employee})