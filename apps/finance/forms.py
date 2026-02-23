from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth import get_user_model
from .models import ReimbursementRequest, ExpenseItem

User = get_user_model()

class ReimbursementRequestForm(forms.ModelForm):
    class Meta:
        model = ReimbursementRequest
        fields = ['title', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
        }

class CheckerSelectionForm(forms.Form):
    checker = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label="Select Checker",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter users who have the 'can_check_reimbursement' permission
        self.fields['checker'].queryset = User.objects.filter(
            user_permissions__codename='can_check_reimbursement',
            user_permissions__content_type__app_label='finance'
        ).distinct()

class ExpenseItemForm(forms.ModelForm):
    class Meta:
        model = ExpenseItem
        fields = ['expense_date', 'expense_type', 'amount', 'currency', 'exchange_rate', 'description', 'attachment']
        widgets = {
            'expense_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'expense_type': forms.Select(attrs={'class': 'form-select'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'exchange_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'description': forms.TextInput(attrs={'placeholder': 'Details about the expense', 'class': 'form-control'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
        }

ExpenseItemFormSet = inlineformset_factory(
    ReimbursementRequest, 
    ExpenseItem, 
    form=ExpenseItemForm,
    extra=1, 
    can_delete=True
)
