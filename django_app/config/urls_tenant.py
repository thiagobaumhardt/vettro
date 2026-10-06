"""URLconf ativo quando um schema de clínica está ativo na sessão
(ver apps/contas/middleware.py: TenantFromSessionMiddleware)."""
from django.urls import include, path

from apps.core.views import health

urlpatterns = [
    path("health", health, name="health"),
    path("", include("apps.dashboard.urls")),
    path("tutores/", include("apps.tutores.urls")),
    path("pacientes/", include("apps.receitas.urls")),  # receitas vivem dentro do paciente
    path("pacientes/", include("apps.pacientes.urls")),
    path("documentos/", include("apps.documentos.urls")),
    path("servicos/", include("apps.financeiro.urls")),
    path("insumos/", include("apps.estoque.urls")),
    path("atendimentos/", include("apps.atendimentos.urls")),
    path("agenda/", include("apps.agenda.urls")),
    path("lembretes/", include("apps.lembretes.urls")),
    path("orcamentos/", include("apps.orcamentos.urls")),
    path("vendas/", include("apps.vendas.urls")),
    path("notas/", include("apps.pagamentos.urls")),
    path("clinica/", include("apps.core.urls")),
    path("auditoria/", include("apps.auditoria.urls")),
    path("usuarios/", include("apps.usuarios_clinica.urls")),
    # login/logout/trocar-de-clínica continuam acessíveis dentro do schema de tenant
    path("", include("apps.contas.urls")),
]
