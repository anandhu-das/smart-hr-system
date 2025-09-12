from django.contrib import admin
from .models import Department, Employee, LeaveRequest, Payroll, Candidate

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['user', 'employee_id', 'department', 'position']
    list_filter = ['department', 'position']
    search_fields = ['user__first_name', 'user__last_name', 'employee_id']

@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['employee', 'start_date', 'end_date', 'status']
    list_filter = ['status', 'start_date']
    search_fields = ['employee__user__first_name', 'employee__user__last_name']

@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ['employee', 'month', 'year', 'net_salary', 'paid']
    list_filter = ['paid', 'month', 'year']
    search_fields = ['employee__user__first_name', 'employee__user__last_name']

@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'position', 'applied_on']
    list_filter = ['position', 'applied_on']
    search_fields = ['name', 'email', 'position']