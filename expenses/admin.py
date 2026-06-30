from django.contrib import admin
from .models import Branch, Expense, BillingReminder, PettyCashDebit


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('location', 'current_balance')


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('date', 'category', 'branch', 'credited_amount', 'debited_amount')
    list_filter = ('category', 'branch', 'date')


@admin.register(BillingReminder)
class BillingReminderAdmin(admin.ModelAdmin):
    list_display = ('title', 'amount', 'frequency', 'due_day', 'is_paid', 'next_due_date')
    list_filter = ('frequency', 'is_paid')


@admin.register(PettyCashDebit)
class PettyCashDebitAdmin(admin.ModelAdmin):
    list_display = ('date', 'amount', 'branch', 'person', 'remark')
    list_filter = ('branch', 'date')
