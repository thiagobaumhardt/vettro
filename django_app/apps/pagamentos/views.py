from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin

from apps.core.decorators import admin_required, requer_secao, secoes_permitidas
from apps.financeiro.models import Cobranca
from apps.vendas.models import Venda

from . import notas
from .models import NotaFiscalEmitida


def _avisar(request, nota):
    if nota.status == "emitida":
        sufixo = " (simulação, sem valor fiscal)" if nota.simulacao else ""
        messages.success(request, f"{nota.get_tipo_display()} nº {nota.numero} emitida{sufixo}.")
    else:
        messages.error(request, f"Nota não autorizada: {nota.mensagem_erro}")


@admin_required
def emitir_cobranca(request, pk):
    cobranca = get_object_or_404(Cobranca, pk=pk)
    if request.method == "POST":
        try:
            _avisar(request, notas.emitir(cobranca=cobranca, clinica_nome=request.session.get("clinica_nome", ""), usuario=request.user))
        except notas.NotaFiscalError as exc:
            messages.error(request, str(exc))
    return redirect(reverse("pacientes:ficha", args=[cobranca.paciente_id]) + "?aba=cobranca")


@requer_secao("vendas")
def emitir_venda(request, pk):
    venda = get_object_or_404(Venda, pk=pk)
    if request.method == "POST":
        try:
            _avisar(request, notas.emitir(venda=venda, clinica_nome=request.session.get("clinica_nome", ""), usuario=request.user))
        except notas.NotaFiscalError as exc:
            messages.error(request, str(exc))
    return redirect("vendas:detalhe", pk=venda.pk)


@xframe_options_sameorigin
def pdf(request, pk):
    """Mesma permissão de quem vê a origem: cobrança é admin; venda, quem vende."""
    nota = get_object_or_404(NotaFiscalEmitida, pk=pk)
    if not request.user.is_authenticated:
        return redirect("contas:login")
    permitido = request.session.get("papel") == "admin" if nota.cobranca_id else "vendas" in secoes_permitidas(request)
    if not permitido:
        raise PermissionDenied("Sem acesso a esta nota.")
    resposta = HttpResponse(notas.pdf_nota(nota, clinica_nome=request.session.get("clinica_nome", "")), content_type="application/pdf")
    resposta["Content-Disposition"] = f'inline; filename="{nota.tipo}-{nota.numero or "nao-autorizada"}.pdf"'
    return resposta
