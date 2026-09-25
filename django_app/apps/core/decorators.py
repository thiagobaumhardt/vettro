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


def secoes_permitidas(request) -> set:
    """Interseção de duas camadas independentes (pedido explícito do
    usuário): o que o PAPEL da pessoa permite (PERMISSOES_POR_PAPEL) E o que
    a CLÍNICA tem habilitado como módulo (Clinica.modulos_habilitados,
    decidido no provisionamento/editável no admin — vale pra todo mundo da
    clínica, inclusive admin). "pacientes_clinico" é sub-permissão de
    "pacientes", não um módulo próprio — só sobrevive ao filtro se
    "pacientes" também estiver habilitado pra clínica."""
    papel = request.session.get("papel") if hasattr(request, "session") else None
    papel_secoes = PERMISSOES_POR_PAPEL.get(papel, set())

    modulos_clinica = request.session.get("modulos_habilitados") if hasattr(request, "session") else None
    if modulos_clinica is None:
        # Sessão sem essa chave (ex: sessão antiga de antes desta feature) —
        # não bloqueia nada por omissão, comportamento antigo preservado.
        return papel_secoes

    modulos_clinica = set(modulos_clinica)
    permitido = {s for s in papel_secoes if s in modulos_clinica}
    if "pacientes_clinico" in papel_secoes and "pacientes" in modulos_clinica:
        permitido.add("pacientes_clinico")
    return permitido


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
    """Restringe uma view a quem tem `secao` liberada — pelo papel E pela
    clínica ter esse módulo habilitado (ver secoes_permitidas)."""

    def decorador(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if secao not in secoes_permitidas(request):
                raise PermissionDenied("Esta área não está disponível — verifique seu perfil ou se o módulo está habilitado pra sua clínica.")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorador
