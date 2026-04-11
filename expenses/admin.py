from django.contrib import admin
from .models import Branch, Expense


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'current_balance')


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('date', 'category', 'branch', 'credited_amount', 'debited_amount')
    list_filter = ('category', 'branch', 'date')
