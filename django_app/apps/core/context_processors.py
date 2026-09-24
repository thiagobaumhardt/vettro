def clinica_ativa(request):
    """Deixa nome da clínica/papel disponíveis em todo template sem repetir
    em cada view (usado pela sidebar/topbar/tabs da Ficha)."""
    from .decorators import secoes_permitidas

    papel = request.session.get("papel") if hasattr(request, "session") else None
    return {
        "clinica_nome_ativa": request.session.get("clinica_nome") if hasattr(request, "session") else None,
        "papel_ativo": papel,
        "secoes_permitidas": secoes_permitidas(papel),
    }
