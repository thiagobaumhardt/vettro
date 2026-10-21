"""URLconf ativo quando NENHUM schema de clínica está ativo na sessão
(ver apps/contas/middleware.py: TenantFromSessionMiddleware)."""
from django.contrib import admin
from django.urls import include, path

from apps.core.views import health
from apps.whatsapp.webhook import webhook as whatsapp_webhook

urlpatterns = [
    path("health", health, name="health"),
    path("plataforma/", admin.site.urls),
    # Webhook da Meta (chega sem sessão — sempre neste URLconf), um só pra todas as clínicas.
    path("whatsapp/webhook/", whatsapp_webhook, name="whatsapp_webhook"),
    path("", include("apps.contas.urls")),
]
