from django import forms
from .models import LeaveApplication
from datetime import datetime

class LeaveApplicationForm(forms.ModelForm):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=False,
        label="Start Date"
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=False,
        label="End Date"
    )
    specific_dates = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'YYYY-MM-DD, YYYY-MM-DD'}),
        required=False,
        label="Specific Dates (for discontinuous leave)",
        help_text="Enter dates separated by comma. If used, Start Date and End Date will be ignored."
    )

    class Meta:
        model = LeaveApplication
        fields = ['leave_type', 'start_date', 'end_date', 'specific_dates', 'reason']
        widgets = {
            'leave_type': forms.Select(attrs={'class': 'form-select'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        specific_dates_str = cleaned_data.get('specific_dates')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if specific_dates_str:
            dates = []
            try:
                for d_str in specific_dates_str.split(','):
                    d_str = d_str.strip()
                    if d_str:
                        dates.append(datetime.strptime(d_str, '%Y-%m-%d').date())
            except ValueError:
                self.add_error('specific_dates', "Invalid date format. Use YYYY-MM-DD, separated by commas.")
                return cleaned_data
            
            if not dates:
                 self.add_error('specific_dates', "Please enter valid dates.")
                 return cleaned_data

            dates.sort()
            cleaned_data['start_date'] = dates[0]
            cleaned_data['end_date'] = dates[-1]
            cleaned_data['parsed_dates'] = dates
            
        else:
            if not start_date or not end_date:
                self.add_error('start_date', "Start date is required if no specific dates provided.")
                self.add_error('end_date', "End date is required if no specific dates provided.")
            elif start_date > end_date:
                self.add_error('end_date', "End date cannot be earlier than start date")

        return cleaned_data
