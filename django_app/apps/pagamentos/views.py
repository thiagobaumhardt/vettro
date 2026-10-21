from datetime import date, timedelta

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin

from apps.core.decorators import admin_required, requer_secao, secoes_permitidas
from apps.financeiro.models import Cobranca
from apps.vendas.models import Venda

from . import contabilidade as contabilidade_svc
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


@requer_secao("recepcao")
def emitir_recebimento(request, pk):
    from apps.financeiro.models import Recebimento

    rec = get_object_or_404(Recebimento, pk=pk)
    if request.method == "POST":
        try:
            _avisar(request, notas.emitir(recebimento=rec, clinica_nome=request.session.get("clinica_nome", ""), usuario=request.user))
        except notas.NotaFiscalError as exc:
            messages.error(request, str(exc))
    return redirect("recepcao:recibo", pk=rec.pk)


@requer_secao("vendas")
def emitir_venda(request, pk):
    venda = get_object_or_404(Venda, pk=pk)
    if request.method == "POST":
        try:
            _avisar(request, notas.emitir(venda=venda, clinica_nome=request.session.get("clinica_nome", ""), usuario=request.user))
        except notas.NotaFiscalError as exc:
            messages.error(request, str(exc))
    return redirect("vendas:detalhe", pk=venda.pk)


def _mes_escolhido(request) -> tuple[int, int]:
    """?mes=2026-10; sem ele (ou inválido), o mês anterior — o que o contador pede."""
    try:
        ano, mes = (int(p) for p in request.GET.get("mes", "").split("-"))
        date(ano, mes, 1)
        return ano, mes
    except ValueError:
        anterior = date.today().replace(day=1) - timedelta(days=1)
        return anterior.year, anterior.month


@admin_required
def contabilidade(request):
    ano, mes = _mes_escolhido(request)
    notas_mes = contabilidade_svc.notas_do_mes(ano, mes)
    return render(request, "pagamentos/contabilidade.html", {
        "mes_valor": f"{ano}-{mes:02d}", "mes_rotulo": f"{mes:02d}/{ano}",
        "resumo": contabilidade_svc.resumo(notas_mes), "notas": notas_mes,
    })


@admin_required
def contabilidade_zip(request):
    ano, mes = _mes_escolhido(request)
    resposta = HttpResponse(
        contabilidade_svc.gerar_zip(ano, mes, request.session.get("clinica_nome", "")), content_type="application/zip",
    )
    resposta["Content-Disposition"] = f'attachment; filename="notas-fiscais-{ano}-{mes:02d}.zip"'
    return resposta


@xframe_options_sameorigin
def pdf(request, pk):
    """Mesma permissão de quem vê a origem: cobrança é admin; venda, quem vende."""
    nota = get_object_or_404(NotaFiscalEmitida, pk=pk)
    if not request.user.is_authenticated:
        return redirect("contas:login")
    if nota.recebimento_id:
        permitido = "recepcao" in secoes_permitidas(request)
    elif nota.cobranca_id:
        permitido = request.session.get("papel") == "admin"
    else:
        permitido = "vendas" in secoes_permitidas(request)
    if not permitido:
        raise PermissionDenied("Sem acesso a esta nota.")
    resposta = HttpResponse(notas.pdf_nota(nota, clinica_nome=request.session.get("clinica_nome", "")), content_type="application/pdf")
    resposta["Content-Disposition"] = f'inline; filename="{nota.tipo}-{nota.numero or "nao-autorizada"}.pdf"'
    return resposta
