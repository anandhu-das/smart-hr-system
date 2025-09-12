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

class Payroll(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    month = models.CharField(max_length=20)
    year = models.IntegerField()
    basic_salary = models.DecimalField(max_digits=10, decimal_places=2)
    allowances = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=10, decimal_places=2)
    paid = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Payslip'
        verbose_name_plural = 'Payslips'
    
    def __str__(self):
        return f"{self.employee} - {self.month}/{self.year}"

class Candidate(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    position = models.CharField(max_length=100)
    cv = models.FileField(upload_to='cvs/')
    applied_on = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name