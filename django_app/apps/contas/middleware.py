from django.conf import settings
from django.db import connection


class TenantFromSessionMiddleware:
    """Substitui o TenantMainMiddleware padrão do django-tenants (que resolve
    o tenant pelo host da requisição). Aqui a clínica ativa é resolvida pela
    SESSÃO — decisão confirmada: domínio único www.vettro.com.br, clínica
    escolhida no login, igual ao SimplesVet (ver §4 do plano).

    Precisa rodar logo após SessionMiddleware e antes de qualquer código que
    faça query no ORM (inclusive AuthenticationMiddleware)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        schema_name = request.session.get("clinica_schema_name")

        if schema_name:
            connection.set_schema(schema_name)
            request.urlconf = settings.URLCONF_TENANT
            request.clinica_id = request.session.get("clinica_id")
            request.clinica_nome = request.session.get("clinica_nome")
        else:
            connection.set_schema_to_public()
            request.urlconf = settings.URLCONF_PUBLIC
            request.clinica_id = None
            request.clinica_nome = None

        return self.get_response(request)
