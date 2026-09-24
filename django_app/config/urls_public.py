"""URLconf ativo quando NENHUM schema de clínica está ativo na sessão
(ver apps/contas/middleware.py: TenantFromSessionMiddleware)."""
from django.contrib import admin
from django.urls import include, path

from apps.core.views import health

urlpatterns = [
    path("health", health, name="health"),
    path("plataforma/", admin.site.urls),
    path("", include("apps.contas.urls")),
]
