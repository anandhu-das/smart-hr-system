from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login as auth_login
from django.contrib import messages
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
import io
from django.contrib.auth import logout
from django.db.models import Sum
from datetime import datetime

from .models import Employee, LeaveRequest, Payroll, Candidate, Department
from .forms import LeaveRequestForm, CandidateForm, PayrollForm
from django.contrib.auth.views import LoginView

# Check if user is HR staff - ROBUST VERSION
def is_hr_staff(user):
    """
    Check if user has HR access rights.
    Returns True for:
    1. Staff users (is_staff = True)
    2. Superusers (is_superuser = True) 
    3. Employees in HR department (department name contains 'hr')
    """
    # Allow staff and superusers immediately
    if user.is_staff or user.is_superuser:
        return True
    
    # Check if user has employee record in HR department
    try:
        employee = Employee.objects.get(user=user)
        if employee.department:
            # Flexible check for HR department (case-insensitive, partial match)
            department_name = employee.department.name.lower()
            hr_keywords = ['hr', 'human resource', 'human resources']
            if any(keyword in department_name for keyword in hr_keywords):
                return True
    except Employee.DoesNotExist:
        # No employee record found
        pass
    
    return False

# Custom Login View
class CustomLoginView(LoginView):
    def get_success_url(self):
        # Check if user is staff/HR, redirect to appropriate dashboard
        if self.request.user.is_staff or self.request.user.is_superuser or is_hr_staff(self.request.user):
            return '/hr/dashboard/'
        else:
            return '/employee/dashboard/'

def home(request):
    return render(request, 'hr_app/home.html')

# Employee Dashboard
@login_required
def employee_dashboard(request):
    try:
        employee = Employee.objects.get(user=request.user)
        leave_requests = LeaveRequest.objects.filter(employee=employee).order_by('-applied_on')[:5]
        payrolls = Payroll.objects.filter(employee=employee).order_by('-year', '-month')[:3]
        
        context = {
            'employee': employee,
            'leave_requests': leave_requests,
            'payrolls': payrolls,
        }
        return render(request, 'hr_app/employee_dashboard.html', context)
    except Employee.DoesNotExist:
        messages.info(request, 'Please complete your employee profile.')
        return render(request, 'hr_app/employee_dashboard.html')

# HR Admin Dashboard
@login_required
@user_passes_test(is_hr_staff)
def hr_dashboard(request):
    total_employees = Employee.objects.count()
    pending_leaves = LeaveRequest.objects.filter(status='Pending').count()
    total_departments = Department.objects.count()
    recent_candidates = Candidate.objects.order_by('-applied_on')[:5]
    
    context = {
        'total_employees': total_employees,
        'pending_leaves': pending_leaves,
        'total_departments': total_departments,
        'recent_candidates': recent_candidates,
    }
    return render(request, 'hr_app/hr_dashboard.html', context)

# Leave Application
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
            try:
                employee = Employee.objects.get(user=request.user)
                leave_request = form.save(commit=False)
                leave_request.employee = employee
                leave_request.save()
                messages.success(request, 'Leave application submitted successfully!')
                return redirect('employee_dashboard')
            except Employee.DoesNotExist:
                messages.error(request, 'Employee profile not found. Please contact HR.')
                return redirect('employee_dashboard')
    else:
        form = LeaveRequestForm()
    
    return render(request, 'hr_app/apply_leave.html', {
        'form': form,
        'leave_requests': leave_requests
    })

# Leave History for Employee
@login_required
def leave_history(request):
    try:
        employee = Employee.objects.get(user=request.user)
        leaves = LeaveRequest.objects.filter(employee=employee).order_by('-applied_on')
        return render(request, 'hr_app/leave_history.html', {'leaves': leaves})
    except Employee.DoesNotExist:
        messages.error(request, 'Employee profile not found.')
        return render(request, 'hr_app/leave_history.html', {'leaves': []})

# HR: Manage All Leaves
@login_required
@user_passes_test(is_hr_staff)
def manage_leaves(request):
    pending_leaves = LeaveRequest.objects.filter(status='Pending').order_by('applied_on')
    approved_leaves = LeaveRequest.objects.filter(status='Approved').order_by('-applied_on')[:10]
    rejected_leaves = LeaveRequest.objects.filter(status='Rejected').order_by('-applied_on')[:10]
    
    context = {
        'pending_leaves': pending_leaves,
        'approved_leaves': approved_leaves,
        'rejected_leaves': rejected_leaves,
    }
    return render(request, 'hr_app/manage_leaves.html', context)

# HR: Approve Leave
@login_required
@user_passes_test(is_hr_staff)
def approve_leave(request, leave_id):
    leave = get_object_or_404(LeaveRequest, id=leave_id)
    leave.status = 'Approved'
    leave.save()
    messages.success(request, f'Leave for {leave.employee.user.get_full_name()} has been approved.')
    return redirect('manage_leaves')

# HR: Reject Leave
@login_required
@user_passes_test(is_hr_staff)
def reject_leave(request, leave_id):
    leave = get_object_or_404(LeaveRequest, id=leave_id)
    leave.status = 'Rejected'
    leave.save()
    messages.success(request, f'Leave for {leave.employee.user.get_full_name()} has been rejected.')
    return redirect('manage_leaves')

# Payslips View
@login_required
def view_payslips(request):
    try:
        employee = Employee.objects.get(user=request.user)
        payrolls = Payroll.objects.filter(employee=employee).order_by('-year', '-month')
        return render(request, 'hr_app/payslips.html', {'payrolls': payrolls})
    except Employee.DoesNotExist:
        messages.error(request, 'Employee profile not found.')
        return render(request, 'hr_app/payslips.html', {'payrolls': []})

# Generate PDF Payslip
@login_required
def generate_payslip_pdf(request, payroll_id):
    try:
        payroll = Payroll.objects.get(id=payroll_id, employee__user=request.user)
        
        # Create PDF
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        
        # Add content to PDF
        p.setFont("Helvetica-Bold", 16)
        p.drawString(1 * inch, 10 * inch, "SMART-HR PAYSLIP")
        p.setFont("Helvetica", 12)
        p.drawString(1 * inch, 9.5 * inch, f"Employee: {payroll.employee.user.get_full_name()}")
        p.drawString(1 * inch, 9 * inch, f"Employee ID: {payroll.employee.employee_id}")
        p.drawString(1 * inch, 8.5 * inch, f"Period: {payroll.month} {payroll.year}")
        p.drawString(1 * inch, 8 * inch, f"Basic Salary: ₹{payroll.basic_salary}")
        p.drawString(1 * inch, 7.5 * inch, f"Allowances: ₹{payroll.allowances}")
        p.drawString(1 * inch, 7 * inch, f"Deductions: ₹{payroll.deductions}")
        p.drawString(1 * inch, 6.5 * inch, f"Net Salary: ₹{payroll.net_salary}")
        p.drawString(1 * inch, 6 * inch, f"Status: {'Paid' if payroll.paid else 'Pending'}")
        
        p.showPage()
        p.save()
        
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="payslip_{payroll.month}_{payroll.year}.pdf"'
        return response
        
    except Payroll.DoesNotExist:
        messages.error(request, 'Payslip not found.')
        return redirect('view_payslips')

# Candidate Registration
def candidate_registration(request):
    if request.method == 'POST':
        form = CandidateForm(request.POST, request.FILES)
        if form.is_valid():
            candidate = form.save()
            messages.success(request, f'Application submitted successfully! Your reference ID is {candidate.id}.')
            return redirect('home')
    else:
        form = CandidateForm()
    
    return render(request, 'hr_app/candidate_registration.html', {'form': form})

# Candidate List (HR View)
@login_required
@user_passes_test(is_hr_staff)
def candidate_list(request):
    candidates = Candidate.objects.all().order_by('-applied_on')
    return render(request, 'hr_app/candidate_list.html', {'candidates': candidates})

@login_required
def custom_logout(request):
    """Custom logout view that redirects to homepage with success message"""
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('home')

# Payroll Views
@login_required
@user_passes_test(is_hr_staff)
def payroll_dashboard(request):
    """HR Payroll Dashboard"""
    recent_payrolls = Payroll.objects.select_related('employee').order_by('-year', '-month')[:10]
    pending_payments = Payroll.objects.filter(paid=False).count()
    total_paid = Payroll.objects.filter(paid=True).aggregate(Sum('net_salary'))['net_salary__sum'] or 0
    
    context = {
        'recent_payrolls': recent_payrolls,
        'pending_payments': pending_payments,
        'total_paid': total_paid,
    }
    return render(request, 'hr_app/payroll_dashboard.html', context)

@login_required
@user_passes_test(is_hr_staff)
def manage_payroll(request):
    """Manage all payroll records"""
    payrolls = Payroll.objects.select_related('employee').order_by('-year', '-month')
    
    # Filtering
    month_filter = request.GET.get('month')
    year_filter = request.GET.get('year')
    status_filter = request.GET.get('status')
    
    if month_filter:
        payrolls = payrolls.filter(month=month_filter)
    if year_filter:
        payrolls = payrolls.filter(year=year_filter)
    if status_filter:
        if status_filter == 'paid':
            payrolls = payrolls.filter(paid=True)
        elif status_filter == 'pending':
            payrolls = payrolls.filter(paid=False)
    
    context = {
        'payrolls': payrolls,
        'months': ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December'],
        'years': range(2020, 2031),
    }
    return render(request, 'hr_app/manage_payroll.html', context)

@login_required
@user_passes_test(is_hr_staff)
def create_payroll(request, employee_id=None):
    """Create or edit payroll for an employee"""
    employee = None
    if employee_id:
        employee = get_object_or_404(Employee, id=employee_id)
    
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
        initial = {}
        if employee:
            initial = {
                'basic_salary': employee.salary,
                'overtime_rate': employee.salary / 200 if employee.salary else 0
            }
        form = PayrollForm(initial=initial)
    
    context = {
        'form': form,
        'employee': employee,
    }
    return render(request, 'hr_app/create_payroll.html', context)

@login_required
@user_passes_test(is_hr_staff)
def edit_payroll(request, payroll_id):
    """Edit existing payroll"""
    payroll = get_object_or_404(Payroll, id=payroll_id)
    
    if request.method == 'POST':
        form = PayrollForm(request.POST, instance=payroll)
        if form.is_valid():
            form.save()
            messages.success(request, f'Payroll updated for {payroll.employee}')
            return redirect('manage_payroll')
    else:
        form = PayrollForm(instance=payroll)
    
    context = {
        'form': form,
        'payroll': payroll,
    }
    return render(request, 'hr_app/edit_payroll.html', context)

@login_required
@user_passes_test(is_hr_staff)
def delete_payroll(request, payroll_id):
    """Delete payroll record"""
    payroll = get_object_or_404(Payroll, id=payroll_id)
    if request.method == 'POST':
        payroll.delete()
        messages.success(request, 'Payroll record deleted successfully')
        return redirect('manage_payroll')
    
    return render(request, 'hr_app/delete_payroll.html', {'payroll': payroll})

@login_required
@user_passes_test(is_hr_staff)
def generate_payroll_pdf(request, payroll_id):
    """Generate PDF payslip"""
    payroll = get_object_or_404(Payroll, id=payroll_id)
    
    # Create PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    
    styles = getSampleStyleSheet()
    elements = []
    
    # Company Header
    company_style = ParagraphStyle(
        'CompanyStyle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=1
    )
    elements.append(Paragraph('SMART-HR MANAGEMENT SYSTEM', company_style))
    elements.append(Paragraph('PAYSLIP', styles['Heading2']))
    elements.append(Spacer(1, 20))
    
    # Employee Details
    employee_data = [
        ['Employee Name', payroll.employee.user.get_full_name()],
        ['Employee ID', payroll.employee.employee_id],
        ['Designation', payroll.employee.position],
        ['Department', str(payroll.employee.department)],
        ['Payment Month', f'{payroll.month} {payroll.year}'],
    ]
    
    employee_table = Table(employee_data, colWidths=[2*inch, 3*inch])
    employee_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(employee_table)
    elements.append(Spacer(1, 20))
    
    # Salary Details
    employee_pf, employer_pf = payroll.calculate_epf()
    overtime_pay = payroll.overtime_hours * payroll.overtime_rate
    
    earnings_data = [
        ['EARNINGS', 'AMOUNT (₹)', 'DEDUCTIONS', 'AMOUNT (₹)'],
        ['Basic Salary', f'{payroll.basic_salary:.2f}', 'Employee PF', f'{employee_pf:.2f}'],
        ['HRA', f'{payroll.house_rent_allowance:.2f}', 'Professional Tax', f'{payroll.professional_tax:.2f}'],
        ['Travel Allowance', f'{payroll.travel_allowance:.2f}', 'Income Tax', f'{payroll.income_tax:.2f}'],
        ['Medical Allowance', f'{payroll.medical_allowance:.2f}', 'Other Deductions', f'{payroll.other_deductions:.2f}'],
        ['Special Allowance', f'{payroll.special_allowance:.2f}', '', ''],
        ['Overtime Pay', f'{overtime_pay:.2f}', '', ''],
        ['', '', '', ''],
        ['Total Earnings', f'{payroll.calculate_total_earnings():.2f}', 'Total Deductions', f'{payroll.calculate_total_deductions():.2f}'],
    ]
    
    salary_table = Table(earnings_data, colWidths=[1.5*inch, 1*inch, 1.5*inch, 1*inch])
    salary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
    ]))
    elements.append(salary_table)
    elements.append(Spacer(1, 20))
    
    # Net Salary
    net_salary_data = [
        ['NET SALARY', f'₹{payroll.net_salary:.2f}'],
    ]
    
    net_salary_table = Table(net_salary_data, colWidths=[2*inch, 2*inch])
    net_salary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
    ]))
    elements.append(net_salary_table)
    
    # Payment Status
    status = "PAID" if payroll.paid else "PENDING"
    status_color = colors.green if payroll.paid else colors.red
    
    status_data = [
        ['PAYMENT STATUS', status],
    ]
    
    status_table = Table(status_data, colWidths=[2*inch, 2*inch])
    status_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), status_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
    ]))
    elements.append(status_table)
    
    # Footer
    elements.append(Spacer(1, 30))
    elements.append(Paragraph('This is a computer-generated payslip. No signature required.', styles['Italic']))
    elements.append(Paragraph(f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', styles['Italic']))
    
    # Build PDF
    doc.build(elements)
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="payslip_{payroll.employee.employee_id}_{payroll.month}_{payroll.year}.pdf"'
    return response

@login_required
@user_passes_test(is_hr_staff)
def bulk_payroll_generation(request):
    """Generate payroll for multiple employees at once"""
    if request.method == 'POST':
        # Add your bulk payroll generation logic here
        # For example:
        # selected_employees = request.POST.getlist('employees')
        # month = request.POST.get('month')
        # year = request.POST.get('year')
        # for employee_id in selected_employees:
        #     employee = Employee.objects.get(id=employee_id)
        #     # Create payroll for each employee
        messages.success(request, 'Bulk payroll generation initiated.')
        return redirect('payroll_dashboard')
    else:
        employees = Employee.objects.all()
        return render(request, 'hr_app/bulk_payroll.html', {'employees': employees})
    
    # In your views.py, add this debug view to check permissions
@login_required
def check_permissions(request):
    user = request.user
    return HttpResponse(f"""
        Username: {user.username}<br>
        Is Staff: {user.is_staff}<br>
        Is Superuser: {user.is_superuser}<br>
        Is HR Staff (according to function): {is_hr_staff(user)}<br>
        Employee Department: {getattr(getattr(user, 'employee', None), 'department', 'No employee record')}
    """)