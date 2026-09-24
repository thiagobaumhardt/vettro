from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

# Perfis pré-definidos (§9-bis do plano) — equivalentes aos "perfis modelo"
# do SimplesVet (veterinário/recepcionista/gestor), não um construtor de
# permissão livre por funcionalidade. "pacientes_clinico" cobre as abas
# médicas da Ficha (Anamnese/Cirurgia/Exames/Fotos) — Notas/Ficha básica
# ficam só em "pacientes".
PERMISSOES_POR_PAPEL = {
    "admin": {"tutores", "pacientes", "pacientes_clinico", "agenda", "atendimentos", "financeiro", "estoque"},
    "vet": {"tutores", "pacientes", "pacientes_clinico", "agenda", "atendimentos", "financeiro", "estoque"},
    "atendente": {"tutores", "pacientes", "agenda"},
    "motorista": {"agenda"},
}


def secoes_permitidas(papel: str) -> set:
    return PERMISSOES_POR_PAPEL.get(papel, set())


def admin_required(view_func):
    """Ação restrita ao admin da clínica de verdade (Usuários, Auditoria,
    Cobrança, Consultórios) — não confundir com requer_secao, que é sobre
    quais MÓDULOS um perfil não-admin pode ver."""

    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if request.session.get("papel") != "admin":
            raise PermissionDenied("Ação restrita a administradores da clínica.")
        return view_func(request, *args, **kwargs)

    return _wrapped


def requer_secao(secao: str):
    """Restringe uma view a perfis cujo PERMISSOES_POR_PAPEL inclui `secao`
    — ex: motorista só tem "agenda", então qualquer view de Pacientes/
    Tutores/Financeiro/Estoque decorada com outra seção nega acesso a ele."""

    def decorador(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if secao not in secoes_permitidas(request.session.get("papel")):
                raise PermissionDenied("Seu perfil não tem acesso a esta área.")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorador
