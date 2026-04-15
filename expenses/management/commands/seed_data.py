import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from expenses.models import Branch, Expense


class Command(BaseCommand):
    help = 'Seed database with sample branches and expenses'

    def handle(self, *args, **options):
        self.stdout.write('Seeding database...')

        # Create branches (identified by location)
        locations = ['Chennai', 'Delhi', 'Mumbai', 'Bangalore', 'Kolkata']

        branches = []
        for loc in locations:
            branch, created = Branch.objects.get_or_create(location=loc)
            branches.append(branch)
            action = 'Created' if created else 'Exists'
            self.stdout.write(f'  {action}: {branch}')

        # Create expenses
        categories = ['Petrol', 'Food', 'Travel', 'Snacks', 'Misc']
        credit_remarks = [
            'Fund allocation', 'Monthly budget', 'Quarterly funding',
            'Emergency fund', 'Project budget', 'Reimbursement',
            'Client payment received', 'Annual budget release',
        ]
        debit_remarks = [
            'Fuel for delivery', 'Team lunch', 'Client visit travel',
            'Office snacks', 'Stationery purchase', 'Vehicle maintenance',
            'Internet bill', 'Software subscription', 'Office rent',
            'Courier charges', 'Marketing expense', 'Staff transport',
        ]

        # Generate 60 expenses over the last 6 months
        today = date.today()
        start_date = today - timedelta(days=180)

        expenses_created = 0
        for i in range(60):
            expense_date = start_date + timedelta(days=random.randint(0, 180))
            branch = random.choice(branches)
            category = random.choice(categories)

            # Randomly decide credit or debit (30% credit, 70% debit)
            is_credit = random.random() < 0.3

            if is_credit:
                credited_amount = Decimal(str(random.randint(5000, 50000)))
                debited_amount = None
                credit_remark = random.choice(credit_remarks)
                debit_remark = ''
            else:
                credited_amount = None
                debited_amount = Decimal(str(random.randint(100, 10000)))
                credit_remark = ''
                debit_remark = random.choice(debit_remarks)

            Expense.objects.create(
                date=expense_date,
                category=category,
                branch=branch,
                credited_amount=credited_amount,
                credit_remark=credit_remark,
                debited_amount=debited_amount,
                debit_remark=debit_remark,
            )
            expenses_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully seeded {len(branches)} branches and {expenses_created} expenses'
            )
        )
