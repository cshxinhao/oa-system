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
    half_day_period = forms.ChoiceField(
        choices=(("", "---------"),) + LeaveApplication.HALF_DAY_PERIOD_CHOICES,
        required=False,
        label="Half Day Period",
        help_text="Required only for half-day leave.",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = LeaveApplication
        fields = ['leave_type', 'is_half_day', 'half_day_period', 'start_date', 'end_date', 'specific_dates', 'reason']
        widgets = {
            'leave_type': forms.Select(attrs={'class': 'form-select'}),
            'is_half_day': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        specific_dates_str = cleaned_data.get('specific_dates')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        is_half_day = cleaned_data.get('is_half_day')
        half_day_period = cleaned_data.get('half_day_period')

        if is_half_day:
            if not half_day_period:
                self.add_error('half_day_period', "Please indicate whether this half-day leave is AM or PM.")
            if start_date and end_date and start_date != end_date:
                self.add_error('end_date', "For half-day leave, start date and end date must be the same.")
            elif specific_dates_str and len(specific_dates_str.split(',')) > 1:
                self.add_error('specific_dates', "For half-day leave, you can only select one date.")
        else:
            cleaned_data['half_day_period'] = None

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
