from apps.core.decorators import admin_required

from .models import AuditLog


@admin_required
def lista(request):
    from django.shortcuts import render

    entidade = request.GET.get("entidade", "")
    logs = AuditLog.objects.all()
    if entidade:
        logs = logs.filter(entidade=entidade)
    logs = logs[:500]

    contexto = {"logs": logs, "entidade": entidade, "entidades": AuditLog.ENTIDADE_CHOICES}
    template = "auditoria/_lista_resultado.html" if request.headers.get("HX-Request") else "auditoria/lista.html"
    return render(request, template, contexto)
