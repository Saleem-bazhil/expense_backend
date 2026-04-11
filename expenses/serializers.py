from rest_framework import serializers
from .models import Branch, Expense


class BranchSerializer(serializers.ModelSerializer):
    current_balance = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = Branch
        fields = ['id', 'name', 'location', 'current_balance', 'created_at']


class ExpenseSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    running_balance = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True, required=False
    )

    class Meta:
        model = Expense
        fields = [
            'id', 'date', 'category', 'branch', 'branch_name',
            'credited_amount', 'credit_remark',
            'debited_amount', 'debit_remark',
            'running_balance', 'created_at',
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

    class Meta:
        model = Expense
        fields = [
            'id', 'date', 'category', 'branch',
            'credited_amount', 'credit_remark',
            'debited_amount', 'debit_remark',
        ]

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

        return data
