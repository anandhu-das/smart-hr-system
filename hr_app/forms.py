from django import forms
from .models import LeaveRequest, Candidate

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
        fields = ['name', 'email', 'position', 'cv']