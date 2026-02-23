from django import forms
from django.forms import inlineformset_factory
from .models import ReimbursementRequest, ExpenseItem

class ReimbursementRequestForm(forms.ModelForm):
    class Meta:
        model = ReimbursementRequest
        fields = ['title', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
        }

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
