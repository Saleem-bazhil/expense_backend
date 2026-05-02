import csv
from datetime import datetime
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import authenticate
from django.db.models import Sum, Q, F, Window
from django.db.models.functions import Coalesce, TruncMonth
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from rest_framework.pagination import PageNumberPagination

from .models import Branch, Expense, PaymentModeBalance, BillingReminder
from .serializers import BranchSerializer, ExpenseSerializer, ExpenseCreateSerializer, PaymentModeBalanceSerializer, BillingReminderSerializer


class ExpensePagination(PageNumberPagination):
    """Pagination that exposes `page_size` in every response — lets the
    frontend compute total pages without hardcoding the size."""

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'page_size': self.get_page_size(self.request),
            'results': data,
        })


class BranchViewSet(viewsets.ModelViewSet):
    """CRUD for branches."""
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    pagination_class = None


class ExpenseViewSet(viewsets.ModelViewSet):
    """CRUD for expenses with filtering and running balance."""

    pagination_class = ExpensePagination

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return ExpenseCreateSerializer
        return ExpenseSerializer

    def get_queryset(self):
        qs = Expense.objects.select_related('branch').all()

        # Filter by branch (can be ID or location name)
        branch_val = self.request.query_params.get('branch')
        if branch_val:
            if branch_val.isdigit():
                qs = qs.filter(branch_id=branch_val)
            else:
                qs = qs.filter(branch__location__icontains=branch_val)

        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)

        # Filter by date range
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)

        # Search
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(credit_remark__icontains=search) |
                Q(debit_remark__icontains=search) |
                Q(credit_person__icontains=search) |
                Q(debit_person__icontains=search) |
                Q(category__icontains=search)
            )

        return qs.order_by('date', 'created_at')

    def list(self, request, *args, **kwargs):
        """Override list to include running balance computation."""
        queryset = self.get_queryset()

        # Calculate running balance
        expenses = list(queryset)
        initial_balances = {m.payment_mode: m.initial_balance for m in PaymentModeBalance.objects.all()}
        balances = {}
        for expense in expenses:
            credit = expense.credited_amount or Decimal('0.00')
            debit = expense.debited_amount or Decimal('0.00')
            
            if debit > 0:
                mode = expense.debit_payment_mode or 'Other'
                if mode not in balances:
                    balances[mode] = initial_balances.get(mode, Decimal('0.00'))
                balances[mode] -= debit
                
            if credit > 0:
                mode = expense.credit_payment_mode or 'Other'
                if mode not in balances:
                    balances[mode] = initial_balances.get(mode, Decimal('0.00'))
                balances[mode] += credit
                
            expense.running_balances = balances.copy()

        # Pagination
        page = self.paginate_queryset(expenses)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(expenses, many=True)
        return Response(serializer.data)


@api_view(['GET'])
def dashboard_view(request):
    """Aggregated dashboard stats."""
    qs = Expense.objects.all()

    # Apply same filters
    branch_val = request.query_params.get('branch')
    if branch_val:
        if branch_val.isdigit():
            qs = qs.filter(branch_id=branch_val)
        else:
            qs = qs.filter(branch__location__icontains=branch_val)

    category = request.query_params.get('category')
    if category:
        qs = qs.filter(category=category)

    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)

    totals = qs.aggregate(
        total_credits=Coalesce(Sum('credited_amount'), Decimal('0.00')),
        total_debits=Coalesce(Sum('debited_amount'), Decimal('0.00')),
    )
    
    # Total Balance is the sum of all Payment Mode balances (Company-wide absolute balance)
    total_initial = PaymentModeBalance.objects.aggregate(t=Coalesce(Sum('initial_balance'), Decimal('0.00')))['t']
    global_credits = Expense.objects.aggregate(t=Coalesce(Sum('credited_amount'), Decimal('0.00')))['t']
    global_debits = Expense.objects.aggregate(t=Coalesce(Sum('debited_amount'), Decimal('0.00')))['t']
    total_balance = total_initial + global_credits - global_debits

    # Category breakdown (for pie chart)
    category_data = (
        qs.values('category')
        .annotate(
            total_credit=Coalesce(Sum('credited_amount'), Decimal('0.00')),
            total_debit=Coalesce(Sum('debited_amount'), Decimal('0.00')),
        )
        .order_by('category')
    )

    # Monthly trend (for line chart)
    monthly_data = (
        qs.annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(
            credits=Coalesce(Sum('credited_amount'), Decimal('0.00')),
            debits=Coalesce(Sum('debited_amount'), Decimal('0.00')),
        )
        .order_by('month')
    )

    # Branch-wise (for bar chart and detailed breakdown)
    branch_qs = (
        qs.values('branch__location')
        .annotate(
            total_credit=Coalesce(Sum('credited_amount'), Decimal('0.00')),
            total_debit=Coalesce(Sum('debited_amount'), Decimal('0.00')),
        )
        .order_by('branch__location')
    )

    branch_breakdown = []
    for item in branch_qs:
        location = item['branch__location']
        # Category breakdown for THIS branch (scoped to current filters)
        branch_cats = (
            qs.filter(branch__location=location)
            .values('category')
            .annotate(
                total_credit=Coalesce(Sum('credited_amount'), Decimal('0.00')),
                total_debit=Coalesce(Sum('debited_amount'), Decimal('0.00')),
            )
            .order_by('-total_debit')
        )

        branch_breakdown.append({
            'branch': location,
            'total_credit': str(item['total_credit']),
            'total_debit': str(item['total_debit']),
            'category_breakdown': [
                {
                    'category': c['category'],
                    'total_credit': str(c['total_credit']),
                    'total_debit': str(c['total_debit']),
                }
                for c in branch_cats
            ]
        })

    return Response({
        'total_balance': str(total_balance),
        'total_credits': str(totals['total_credits']),
        'total_debits': str(totals['total_debits']),
        'category_breakdown': [
            {
                'category': item['category'],
                'total_credit': str(item['total_credit']),
                'total_debit': str(item['total_debit']),
            }
            for item in category_data
        ],
        'monthly_trend': [
            {
                'month': item['month'].strftime('%Y-%m') if item['month'] else '',
                'credits': str(item['credits']),
                'debits': str(item['debits']),
            }
            for item in monthly_data
        ],
        'branch_breakdown': branch_breakdown,
    })


@api_view(['GET'])
def export_expenses(request):
    """Export expenses to CSV."""
    qs = Expense.objects.select_related('branch').all().order_by('date', 'created_at')

    # Apply filters
    branch_val = request.query_params.get('branch')
    if branch_val:
        if branch_val.isdigit():
            qs = qs.filter(branch_id=branch_val)
        else:
            qs = qs.filter(branch__location__icontains=branch_val)

    category = request.query_params.get('category')
    if category:
        qs = qs.filter(category=category)

    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)

    # Note: avoid the name `format` — DRF reserves it for content negotiation.
    fmt = request.query_params.get('type', 'csv')

    if fmt == 'excel':
        # Excel export
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = 'Expenses'

            headers = ['S.No', 'Date', 'Category', 'Branch', 'Credit Amount',
                        'Credit Remark', 'Credit Person', 'Credit Payment Mode',
                        'Debit Amount', 'Debit Remark', 'Debit Person',
                        'Debit Payment Mode', 'Running Balance']
            ws.append(headers)

            initial_balances = {m.payment_mode: m.initial_balance for m in PaymentModeBalance.objects.all()}
            balances = {}
            for idx, expense in enumerate(qs, 1):
                credit = expense.credited_amount or Decimal('0.00')
                debit = expense.debited_amount or Decimal('0.00')
                if debit > 0:
                    mode = expense.debit_payment_mode or 'Other'
                    if mode not in balances:
                        balances[mode] = initial_balances.get(mode, Decimal('0.00'))
                    balances[mode] -= debit
                    
                if credit > 0:
                    mode = expense.credit_payment_mode or 'Other'
                    if mode not in balances:
                        balances[mode] = initial_balances.get(mode, Decimal('0.00'))
                    balances[mode] += credit

                running_balance = " | ".join(f"{k}: {float(v)}" for k, v in balances.items() if v != Decimal('0.00'))


                ws.append([
                    idx,
                    expense.date.strftime('%Y-%m-%d'),
                    expense.category,
                    expense.branch.location,
                    float(credit),
                    expense.credit_remark,
                    expense.credit_person,
                    expense.credit_payment_mode,
                    float(debit),
                    expense.debit_remark,
                    expense.debit_person,
                    expense.debit_payment_mode,
                    running_balance,
                ])

            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)

            response = HttpResponse(
                buffer.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="expenses.xlsx"'
            return response
        except ImportError:
            return Response(
                {"error": "openpyxl not installed for Excel export"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    else:
        # CSV export
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="expenses.csv"'

        writer = csv.writer(response)
        writer.writerow(['S.No', 'Date', 'Category', 'Branch', 'Credit Amount',
                          'Credit Remark', 'Credit Person', 'Credit Payment Mode',
                          'Debit Amount', 'Debit Remark', 'Debit Person',
                          'Debit Payment Mode', 'Running Balance'])

        initial_balances = {m.payment_mode: m.initial_balance for m in PaymentModeBalance.objects.all()}
        balances = {}
        for idx, expense in enumerate(qs, 1):
            credit = expense.credited_amount or Decimal('0.00')
            debit = expense.debited_amount or Decimal('0.00')
            if debit > 0:
                mode = expense.debit_payment_mode or 'Other'
                if mode not in balances:
                    balances[mode] = initial_balances.get(mode, Decimal('0.00'))
                balances[mode] -= debit
                
            if credit > 0:
                mode = expense.credit_payment_mode or 'Other'
                if mode not in balances:
                    balances[mode] = initial_balances.get(mode, Decimal('0.00'))
                balances[mode] += credit

            running_balance = " | ".join(f"{k}: {float(v)}" for k, v in balances.items() if v != Decimal('0.00'))


            writer.writerow([
                idx,
                expense.date.strftime('%Y-%m-%d'),
                expense.category,
                expense.branch.location,
                credit,
                expense.credit_remark,
                expense.credit_person,
                expense.credit_payment_mode,
                debit,
                expense.debit_remark,
                expense.debit_person,
                expense.debit_payment_mode,
                running_balance,
            ])

        return response


# ---------------------------------------------------------------------------
# Payment Mode Balances
# ---------------------------------------------------------------------------
@api_view(['GET'])
def payment_mode_balances_view(request):
    """Return all payment modes with initial + current balance, including those only present in expenses.
    
    Supports filtering:
      - fy: Financial year, e.g. '2025-2026' (April to March)
      - date_from / date_to: Custom date range
    """
    # Build expense filter based on query params
    expense_filter = Q()
    fy = request.query_params.get('fy')
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')

    start_date = None
    if fy:
        # Financial year format: '2025-2026' means April 2025 to March 2026
        try:
            parts = fy.split('-')
            start_year = int(parts[0])
            end_year = int(parts[1])
            start_date = f'{start_year}-04-01'
            expense_filter &= Q(date__gte=start_date, date__lte=f'{end_year}-03-31')
        except (ValueError, IndexError):
            pass
    else:
        if date_from:
            expense_filter &= Q(date__gte=date_from)
            start_date = date_from
        if date_to:
            expense_filter &= Q(date__lte=date_to)

    balances = list(PaymentModeBalance.objects.all())
    explicit_modes = {b.payment_mode for b in balances}
    
    credit_modes = Expense.objects.exclude(credit_payment_mode='').values_list('credit_payment_mode', flat=True).distinct()
    debit_modes = Expense.objects.exclude(debit_payment_mode='').values_list('debit_payment_mode', flat=True).distinct()
    
    all_used_modes = set(credit_modes).union(set(debit_modes))
    missing_modes = all_used_modes - explicit_modes
    
    for mode in missing_modes:
        if mode:
            balances.append(PaymentModeBalance(
                id=len(balances) + 9999, # Fake ID to bypass frontend unique key warnings
                payment_mode=mode,
                initial_balance=Decimal('0.00')
            ))

    result = []
    for bal in balances:
        mode = bal.payment_mode
        
        # Calculate initial balance up to just before the selected range
        initial_balance = bal.initial_balance
        if start_date:
            credits_before = Expense.objects.filter(
                date__lt=start_date, credit_payment_mode=mode
            ).aggregate(
                total=Coalesce(Sum('credited_amount'), Decimal('0.00'))
            )['total']
            
            debits_before = Expense.objects.filter(
                date__lt=start_date, debit_payment_mode=mode
            ).aggregate(
                total=Coalesce(Sum('debited_amount'), Decimal('0.00'))
            )['total']
            
            initial_balance = initial_balance + credits_before - debits_before

        # Credits with this payment mode (filtered)
        total_credits = Expense.objects.filter(
            expense_filter, credit_payment_mode=mode
        ).aggregate(
            total=Coalesce(Sum('credited_amount'), Decimal('0.00'))
        )['total']
        # Debits with this payment mode (filtered)
        total_debits = Expense.objects.filter(
            expense_filter, debit_payment_mode=mode
        ).aggregate(
            total=Coalesce(Sum('debited_amount'), Decimal('0.00'))
        )['total']
        
        current = initial_balance + total_credits - total_debits
        bal.initial_balance = initial_balance
        bal.current_balance = current
        bal.total_credits = total_credits
        bal.total_debits = total_debits
        result.append(bal)

    serializer = PaymentModeBalanceSerializer(result, many=True)
    return Response(serializer.data)



@api_view(['POST'])
def payment_mode_balance_set(request):
    """Create or update initial balance for a payment mode."""
    mode = request.data.get('payment_mode', '').strip()
    initial = request.data.get('initial_balance')

    if not mode:
        return Response(
            {'detail': 'payment_mode is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    obj, created = PaymentModeBalance.objects.update_or_create(
        payment_mode=mode,
        defaults={'initial_balance': Decimal(str(initial or 0))},
    )

    # Compute current balance
    total_credits = Expense.objects.filter(
        credit_payment_mode=mode
    ).aggregate(
        total=Coalesce(Sum('credited_amount'), Decimal('0.00'))
    )['total']
    total_debits = Expense.objects.filter(
        debit_payment_mode=mode
    ).aggregate(
        total=Coalesce(Sum('debited_amount'), Decimal('0.00'))
    )['total']
    obj.current_balance = obj.initial_balance + total_credits - total_debits

    serializer = PaymentModeBalanceSerializer(obj)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['DELETE'])
def payment_mode_balance_delete(request):
    """Delete a payment mode balance entry."""
    mode = request.data.get('payment_mode', '').strip()

    if not mode:
        return Response(
            {'detail': 'payment_mode is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        obj = PaymentModeBalance.objects.get(payment_mode=mode)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except PaymentModeBalance.DoesNotExist:
        return Response(
            {'detail': f'Payment mode "{mode}" not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )


# ---------------------------------------------------------------------------
# Categories — expose model choices so the frontend doesn't hardcode them.
# ---------------------------------------------------------------------------
@api_view(['GET'])
def categories_view(request):
    """Single source of truth for expense categories (drawn from the model)."""
    return Response([value for value, _ in Expense.CATEGORY_CHOICES])


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """Username + password → token. Used by the SPA login form."""
    username = (request.data.get('username') or '').strip()
    password = request.data.get('password') or ''

    if not username or not password:
        return Response(
            {'detail': 'Username and password are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(request, username=username, password=password)
    if user is None or not user.is_active:
        return Response(
            {'detail': 'Invalid credentials.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        'token': token.key,
        'username': user.username,
        'is_staff': user.is_staff,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Invalidate the caller's token."""
    Token.objects.filter(user=request.user).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    """Return current user info — used to verify a stored token is still valid."""
    return Response({
        'username': request.user.username,
        'is_staff': request.user.is_staff,
    })


# ---------------------------------------------------------------------------
# Billing Reminders
# ---------------------------------------------------------------------------
@api_view(['GET'])
def billing_reminders_list(request):
    """List all billing reminders."""
    reminders = BillingReminder.objects.all()
    serializer = BillingReminderSerializer(reminders, many=True)
    return Response(serializer.data)


@api_view(['POST'])
def billing_reminder_create(request):
    """Create a new billing reminder."""
    serializer = BillingReminderSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT'])
def billing_reminder_update(request, pk):
    """Update a billing reminder."""
    try:
        reminder = BillingReminder.objects.get(pk=pk)
    except BillingReminder.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = BillingReminderSerializer(reminder, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH'])
def billing_reminder_toggle_paid(request, pk):
    """Toggle the is_paid status of a billing reminder."""
    try:
        reminder = BillingReminder.objects.get(pk=pk)
    except BillingReminder.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    reminder.is_paid = not reminder.is_paid
    reminder.save()
    serializer = BillingReminderSerializer(reminder)
    return Response(serializer.data)


@api_view(['DELETE'])
def billing_reminder_delete(request, pk):
    """Delete a billing reminder."""
    try:
        reminder = BillingReminder.objects.get(pk=pk)
    except BillingReminder.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    reminder.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
