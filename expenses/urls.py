from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'expenses', views.ExpenseViewSet, basename='expense')
router.register(r'branches', views.BranchViewSet, basename='branch')

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('export/', views.export_expenses, name='export'),
    path('categories/', views.categories_view, name='categories'),
    path('payment-mode-balances/', views.payment_mode_balances_view, name='payment-mode-balances'),
    path('payment-mode-balances/set/', views.payment_mode_balance_set, name='payment-mode-balance-set'),
    path('payment-mode-balances/delete/', views.payment_mode_balance_delete, name='payment-mode-balance-delete'),
    path('auth/login/', views.login_view, name='auth-login'),
    path('auth/logout/', views.logout_view, name='auth-logout'),
    path('auth/me/', views.me_view, name='auth-me'),
]
