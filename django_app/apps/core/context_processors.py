def clinica_ativa(request):
    """Deixa nome da clínica/papel disponíveis em todo template sem repetir
    em cada view (usado pela sidebar/topbar/tabs da Ficha)."""
    from .decorators import secoes_permitidas

    return {
        "clinica_nome_ativa": request.session.get("clinica_nome") if hasattr(request, "session") else None,
        "papel_ativo": request.session.get("papel") if hasattr(request, "session") else None,
        "secoes_permitidas": secoes_permitidas(request),
    }
