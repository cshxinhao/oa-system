from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from decimal import Decimal

class ReimbursementRequest(models.Model):
    STATUS_CHOICES = (
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('PAID', 'Paid'),
    )

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='reimbursements',
        verbose_name=_("Requester")
    )
    title = models.CharField(_("Title"), max_length=200, help_text=_("E.g., Business Trip to Tokyo"))
    description = models.TextField(_("Description"), blank=True)
    status = models.CharField(_("Status"), max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='approved_reimbursements',
        verbose_name=_("Approver")
    )
    rejection_reason = models.TextField(_("Rejection Reason"), blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Reimbursement Request")
        verbose_name_plural = _("Reimbursement Requests")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
    
    @property
    def total_amount(self):
        return sum(item.converted_amount for item in self.items.all())

class ExpenseItem(models.Model):
    EXPENSE_TYPES = (
        ('HOTEL', 'Hotel'),
        ('DINING', 'Dining'),
        ('TRAVEL', 'Travel'),
        ('MISC', 'Miscellaneous'),
    )
    CURRENCY_CHOICES = (
        ('HKD', 'HKD'),
        ('USD', 'USD'),
        ('CNY', 'CNY'),
        ('EUR', 'EUR'),
        ('GBP', 'GBP'),
        ('JPY', 'JPY'),
        ('OTHER', 'Other'),
    )

    request = models.ForeignKey(
        ReimbursementRequest, 
        on_delete=models.CASCADE, 
        related_name='items',
        verbose_name=_("Reimbursement Request")
    )
    expense_date = models.DateField(_("Date of Expense"))
    expense_type = models.CharField(_("Type"), max_length=20, choices=EXPENSE_TYPES)
    
    amount = models.DecimalField(_("Amount"), max_digits=12, decimal_places=2)
    currency = models.CharField(_("Currency"), max_length=10, choices=CURRENCY_CHOICES, default='HKD')
    exchange_rate = models.DecimalField(
        _("Exchange Rate"), 
        max_digits=10, 
        decimal_places=4, 
        default=1.0000, 
        help_text=_("Exchange rate to HKD (Base Currency)")
    )
    
    description = models.CharField(_("Description"), max_length=255, blank=True)
    attachment = models.FileField(
        _("Receipt/Invoice"), 
        upload_to='finance/receipts/%Y/%m/', 
        blank=True, 
        null=True
    )

    class Meta:
        verbose_name = _("Expense Item")
        verbose_name_plural = _("Expense Items")
        ordering = ['expense_date']

    @property
    def converted_amount(self):
        if self.amount and self.exchange_rate:
            return round(self.amount * self.exchange_rate, 2)
        return Decimal('0.00')

    def __str__(self):
        return f"{self.get_expense_type_display()} - {self.amount} {self.currency}"
