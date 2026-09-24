from .models import AuditLog


def registrar(*, usuario, acao: str, entidade: str, entidade_id=None, detalhe: str = "", ip: str = "") -> AuditLog:
    """Porte de backend/app/utils.py:registrar_auditoria. `usuario` pode ser
    None (ex: tentativa de login com e-mail que não existe)."""
    return AuditLog.objects.create(
        usuario_id=getattr(usuario, "id", None),
        usuario_nome=getattr(usuario, "nome", ""),
        acao=acao, entidade=entidade, entidade_id=entidade_id, detalhe=detalhe, ip=ip,
    )


def ip_da_requisicao(request) -> str:
    return request.META.get("REMOTE_ADDR", "")
