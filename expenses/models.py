from django.db import models


class Branch(models.Model):
    """Company branch — identified by location."""
    location = models.CharField(max_length=200, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Branches'
        ordering = ['location']

    def __str__(self):
        return self.location

    @property
    def current_balance(self):
        """Calculate balance = total credits - total debits for this branch."""
        from django.db.models import Sum
        totals = self.expenses.aggregate(
            total_credits=Sum('credited_amount'),
            total_debits=Sum('debited_amount'),
        )
        credits = totals['total_credits'] or 0
        debits = totals['total_debits'] or 0
        return credits - debits


class Expense(models.Model):
    """Expense entry model."""
    CATEGORY_CHOICES = [
        ('Petrol', 'Petrol'),
        ('Food', 'Food'),
        ('Travel', 'Travel'),
        ('Snacks', 'Snacks'),
        ('Stationary', 'Stationary'),
        ('Toolkit', 'Toolkit'),
        ('Misc', 'Misc'),
    ]

    date = models.DateField()
    category = models.CharField(max_length=100)
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='expenses',
    )
    credited_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        default=None,
    )
    credit_remark = models.CharField(max_length=300, blank=True, default='')
    credit_person = models.CharField(max_length=200, blank=True, default='')
    credit_payment_mode = models.CharField(
        max_length=30,
        blank=True,
        default='',
        choices=[
            ('Cash', 'Cash'),
            ('Bank Transfer', 'Bank Transfer'),
            ('GPay', 'GPay'),
            ('PhonePe', 'PhonePe'),
            ('UPI', 'UPI'),
            ('Cheque', 'Cheque'),
            ('Other', 'Other'),
        ],
    )
    debited_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        default=None,
    )
    debit_remark = models.CharField(max_length=300, blank=True, default='')
    debit_person = models.CharField(max_length=200, blank=True, default='')
    debit_payment_mode = models.CharField(
        max_length=30,
        blank=True,
        default='',
        choices=[
            ('Cash', 'Cash'),
            ('Bank Transfer', 'Bank Transfer'),
            ('GPay', 'GPay'),
            ('PhonePe', 'PhonePe'),
            ('UPI', 'UPI'),
            ('Cheque', 'Cheque'),
            ('Other', 'Other'),
        ],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.date} | {self.category} | {self.branch.location}"


PAYMENT_MODE_CHOICES = [
    ('Cash', 'Cash'),
    ('Bank Transfer', 'Bank Transfer'),
    ('GPay', 'GPay'),
    ('PhonePe', 'PhonePe'),
    ('UPI', 'UPI'),
    ('Cheque', 'Cheque'),
    ('Other', 'Other'),
]


class PaymentModeBalance(models.Model):
    """Tracks initial balance for each payment mode."""
    payment_mode = models.CharField(
        max_length=30,
        choices=PAYMENT_MODE_CHOICES,
        unique=True,
    )
    initial_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['payment_mode']

    def __str__(self):
        return f"{self.payment_mode}: {self.initial_balance}"
