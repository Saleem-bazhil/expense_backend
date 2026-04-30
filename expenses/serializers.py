from decimal import Decimal
from rest_framework import serializers
from .models import Branch, Expense, PaymentModeBalance, BillingReminder


class BranchSerializer(serializers.ModelSerializer):
    current_balance = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = Branch
        fields = ['id', 'location', 'current_balance', 'created_at']


class ExpenseSerializer(serializers.ModelSerializer):
    branch_location = serializers.CharField(source='branch.location', read_only=True)
    running_balances = serializers.JSONField(read_only=True, required=False)

    class Meta:
        model = Expense
        fields = [
            'id', 'date', 'category', 'branch', 'branch_location',
            'credited_amount', 'credit_remark', 'credit_person', 'credit_payment_mode',
            'debited_amount', 'debit_remark', 'debit_person', 'debit_payment_mode',
            'running_balances', 'created_at',
        ]

    def validate(self, data):
        """Ensure at least one of credit or debit is provided."""
        credit = data.get('credited_amount')
        debit = data.get('debited_amount')

        if not credit and not debit:
            raise serializers.ValidationError(
                "Either credited_amount or debited_amount must be provided."
            )

        if credit is not None and credit < 0:
            raise serializers.ValidationError(
                {"credited_amount": "Amount must be positive."}
            )

        if debit is not None and debit < 0:
            raise serializers.ValidationError(
                {"debited_amount": "Amount must be positive."}
            )

        return data


class ExpenseCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating expenses."""

    branch = serializers.CharField()
    
    class Meta:
        model = Expense
        fields = [
            'id', 'date', 'category', 'branch',
            'credited_amount', 'credit_remark', 'credit_person', 'credit_payment_mode',
            'debited_amount', 'debit_remark', 'debit_person', 'debit_payment_mode',
        ]

    def validate_branch(self, value):
        """Find or create branch by location name."""
        if not value:
            raise serializers.ValidationError("Branch location is required.")
        branch, _ = Branch.objects.get_or_create(location=value)
        return branch

    def validate(self, data):
        credit = data.get('credited_amount')
        debit = data.get('debited_amount')

        if not credit and not debit:
            raise serializers.ValidationError(
                "Either credited_amount or debited_amount must be provided."
            )

        if credit is not None and credit < 0:
            raise serializers.ValidationError(
                {"credited_amount": "Amount must be positive."}
            )

        if debit is not None and debit < 0:
            raise serializers.ValidationError(
                {"debited_amount": "Amount must be positive."}
            )

        if debit is not None and debit > 0:
            mode = data.get('debit_payment_mode') or ''
            if self.instance and not mode:
                mode = self.instance.debit_payment_mode or ''
                
            if mode:
                from .models import PaymentModeBalance
                from django.db.models import Sum
                from django.db.models.functions import Coalesce
                
                try:
                    bal = PaymentModeBalance.objects.get(payment_mode=mode)
                    initial = bal.initial_balance
                except PaymentModeBalance.DoesNotExist:
                    initial = Decimal('0.00')

                total_credits = Expense.objects.filter(credit_payment_mode=mode).aggregate(
                    t=Coalesce(Sum('credited_amount'), Decimal('0.00'))
                )['t']
                total_debits = Expense.objects.filter(debit_payment_mode=mode).aggregate(
                    t=Coalesce(Sum('debited_amount'), Decimal('0.00'))
                )['t']

                current_balance = initial + total_credits - total_debits
                if self.instance and self.instance.debit_payment_mode == mode:
                    current_balance += (self.instance.debited_amount or Decimal('0.00'))

                if current_balance < debit:
                    raise serializers.ValidationError(
                        f"Insufficient funds! You have only \u20b9{current_balance:,.2f} balance in {mode}."
                    )

        return data


class PaymentModeBalanceSerializer(serializers.ModelSerializer):
    current_balance = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True, required=False
    )
    total_credits = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True, required=False
    )
    total_debits = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True, required=False
    )

    class Meta:
        model = PaymentModeBalance
        fields = ['id', 'payment_mode', 'initial_balance', 'current_balance', 'total_credits', 'total_debits']


class BillingReminderSerializer(serializers.ModelSerializer):
    branch_location = serializers.CharField(source='branch.location', read_only=True)

    class Meta:
        model = BillingReminder
        fields = [
            'id', 'title', 'amount', 'due_day', 'frequency',
            'category', 'notes', 'is_paid', 'next_due_date',
            'branch', 'branch_location',
            'created_at', 'updated_at',
        ]
