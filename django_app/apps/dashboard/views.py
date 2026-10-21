from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from apps.core.decorators import secoes_permitidas


@login_required
def inicio(request):
    """Tela inicial. Quem recebe pagamentos (Recepção/admin) vê a fila de
    atendimentos finalizados aguardando pagamento e o que entrou hoje."""
    contexto = {"fila": None}
    if "recepcao" in secoes_permitidas(request):
        from apps.financeiro.models import Recebimento
        from apps.financeiro.recepcao import pendentes_por_tutor

        fila = pendentes_por_tutor()
        hoje = list(Recebimento.objects.filter(criado_em__date=timezone.localdate()).prefetch_related("pagamentos"))
        contexto.update(
            fila=fila, total_fila=sum((g["total"] for g in fila), Decimal("0")),
            recebidos_hoje=hoje, total_hoje=sum((r.total for r in hoje), Decimal("0")),
        )
    return render(request, "dashboard/inicio.html", contexto)
