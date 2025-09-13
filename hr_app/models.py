from django.db import models
from django.contrib.auth.models import User

class Department(models.Model):
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name

class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True)
    position = models.CharField(max_length=100)
    date_joined = models.DateField()
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    contact_number = models.CharField(max_length=15)
    address = models.TextField()
    
    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"

class LeaveRequest(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    applied_on = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.employee} - {self.start_date} to {self.end_date}"

# Add to your existing Payroll model or update it
class Payroll(models.Model):
    EMPLOYEE_CONTRIBUTION = 0.12  # 12% for EPF/PPF
    EMPLOYER_CONTRIBUTION = 0.133  # 13.3% for EPF/PPF
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    month = models.CharField(max_length=20)
    year = models.IntegerField()
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2)
    house_rent_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    travel_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    medical_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    special_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overtime_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    overtime_rate = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    professional_tax = models.DecimalField(max_digits=8, decimal_places=2, default=200)
    income_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    paid = models.BooleanField(default=False)
    payment_date = models.DateField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Payslip'
        verbose_name_plural = 'Payslips'
        unique_together = ['employee', 'month', 'year']
    
    def calculate_epf(self):
        """Calculate Employee and Employer PF contributions"""
        basic_for_pf = min(self.basic_salary, 15000)  # PF limit
        employee_pf = basic_for_pf * self.EMPLOYEE_CONTRIBUTION
        employer_pf = basic_for_pf * self.EMPLOYER_CONTRIBUTION
        return employee_pf, employer_pf
    
    def calculate_total_earnings(self):
        """Calculate total earnings"""
        overtime_pay = self.overtime_hours * self.overtime_rate
        return (self.basic_salary + self.house_rent_allowance + 
                self.travel_allowance + self.medical_allowance + 
                self.special_allowance + overtime_pay)
    
    def calculate_total_deductions(self):
        """Calculate total deductions"""
        employee_pf, employer_pf = self.calculate_epf()
        return employee_pf + self.professional_tax + self.income_tax + self.other_deductions
    
    def save(self, *args, **kwargs):
        # Auto-calculate net salary
        total_earnings = self.calculate_total_earnings()
        total_deductions = self.calculate_total_deductions()
        self.net_salary = total_earnings - total_deductions
        
        # Set overtime rate if not set (default to basic/200)
        if not self.overtime_rate:
            self.overtime_rate = self.basic_salary / 200  # Assuming 200 working hours/month
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.employee} - {self.month}/{self.year} - ₹{self.net_salary}"

class Candidate(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    position = models.CharField(max_length=100)
    cv = models.FileField(upload_to='cvs/')
    applied_on = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name