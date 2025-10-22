from django import forms
from .models import LeaveRequest, Candidate, Payroll, Employee, User


# --- CRITICAL FIX: Define MONTH CHOICES globally ---
MONTH_CHOICES = [
    ('January', 'January'), ('February', 'February'), ('March', 'March'),
    ('April', 'April'), ('May', 'May'), ('June', 'June'),
    ('July', 'July'), ('August', 'August'), ('September', 'September'),
    ('October', 'October'), ('November', 'November'), ('December', 'December')
]


class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['start_date', 'end_date', 'reason']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }


class CandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = ['name', 'email', 'phone', 'position', 'cv', 'cover_letter']
        widgets = {
            'cover_letter': forms.Textarea(attrs={'rows': 4}),
        }


class PayrollForm(forms.ModelForm):
    class Meta:
        model = Payroll
        fields = [
            'employee', 'month', 'year', 'basic_salary', 'house_rent_allowance',
            'travel_allowance', 'medical_allowance', 'special_allowance',
            'overtime_hours', 'overtime_rate', 'professional_tax', 'income_tax',
            'other_deductions', 'paid', 'payment_date'
        ]
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
            # FIX: Use the global constant here
            'month': forms.Select(choices=MONTH_CHOICES),
            'year': forms.NumberInput(attrs={'min': 2020, 'max': 2030}),
        }


class PayrollCalculationForm(forms.Form):
    # FIX: Use the global constant here
    month = forms.ChoiceField(choices=MONTH_CHOICES)
    year = forms.IntegerField(min_value=2020, max_value=2030)


class EmployeeForm(forms.ModelForm):
    # CRITICAL: We need fields for name and email from the User model for editing!
    # These fields are NOT on the Employee model, so we add them manually.
    first_name = forms.CharField(max_length=150, required=True, label="First Name")
    last_name = forms.CharField(max_length=150, required=True, label="Last Name")
    email = forms.EmailField(required=False, label="Email")

    class Meta:
        model = Employee
        fields = [
            'employee_id',
            'department',
            'position',
            'date_joined',
            'salary',
            'contact_number',
            'address',
        ]
        widgets = {
            'date_joined': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
        }
    
    # Overriding __init__ to populate User fields on GET request
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate fields from the linked User model instance (for editing)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
            
    # Overriding save to update BOTH Employee and linked User models
    def save(self, commit=True):
        employee = super().save(commit=False)
        
        # Update linked User fields
        if employee.user:
            employee.user.first_name = self.cleaned_data.get('first_name', employee.user.first_name)
            employee.user.last_name = self.cleaned_data.get('last_name', employee.user.last_name)
            employee.user.email = self.cleaned_data.get('email', employee.user.email)
            employee.user.save()
            
        if commit:
            employee.save()
        return employee