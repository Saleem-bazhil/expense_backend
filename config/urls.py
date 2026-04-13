"""URL configuration for config project."""
from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.urls import path, include


def health(_request):
    """Liveness + DB readiness probe used by Docker/Dokploy."""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        return JsonResponse({'status': 'ok', 'db': 'ok'})
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({'status': 'degraded', 'db': str(exc)}, status=503)


urlpatterns = [
    path('health/', health, name='health'),
    path('admin/', admin.site.urls),
    path('api/', include('expenses.urls')),
]
