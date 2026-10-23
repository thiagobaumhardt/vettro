from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.decorators import admin_required

from . import caixa
from .forms import DespesaForm
from .models import Despesa

ABAS = ("resumo", "entradas", "saidas")


def _render(request, *, despesa_form=None, editando=None, aba=None):
    inicio, fim, mes = caixa.periodo(request.GET)
    lista_entradas = caixa.entradas(inicio, fim)
    lista_saidas = caixa.saidas(inicio, fim)
    lista_reposicoes = caixa.reposicoes(inicio, fim)
    total_reposicoes = sum((r.valor for r in lista_reposicoes), 0)
    total_entradas = sum((e.valor for e in lista_entradas), 0)
    total_saidas = sum((d.valor for d in lista_saidas), 0) + total_reposicoes
    if aba is None:
        aba = request.GET.get("aba") if request.GET.get("aba") in ABAS else "resumo"
    return render(request, "financeiro/caixa.html", {
        "aba_inicial": aba, "inicio": inicio, "fim": fim, "mes": mes,
        "entradas": lista_entradas, "saidas": lista_saidas,
        "reposicoes": lista_reposicoes, "total_reposicoes": total_reposicoes,
        "reposicoes_ignoradas": caixa.reposicoes(inicio, fim, ignoradas=True),
        "qtd_saidas": len(lista_saidas) + len(lista_reposicoes),
        "total_entradas": total_entradas, "total_saidas": total_saidas, "saldo": total_entradas - total_saidas,
        "por_forma": caixa.entradas_por_forma(inicio, fim),
        "por_categoria": caixa.saidas_por_categoria(inicio, fim, total_reposicoes),
        "despesa_form": despesa_form or DespesaForm(instance=editando, initial=None if editando else {"data": timezone.localdate()}),
        "editando": editando,
        "form_aberto": bool(editando or (despesa_form and despesa_form.errors)),
        "periodo_query": request.GET.urlencode(),
    })


@admin_required
def painel(request):
    return _render(request)


def _voltar(request):
    destino = request.POST.get("voltar") or ""
    # Só volta pra dentro do próprio Financeiro (evita redirecionamento aberto).
    return redirect(destino if destino.startswith(reverse("caixa:painel")) else f"{reverse('caixa:painel')}?aba=saidas")


@admin_required
def despesa_salvar(request, pk=None):
    despesa = get_object_or_404(Despesa, pk=pk) if pk else None
    if request.method == "POST":
        form = DespesaForm(request.POST, request.FILES, instance=despesa)
        if form.is_valid():
            obj = form.save(commit=False)
            if "comprovante" in request.FILES:
                obj.comprovante_nome = request.FILES["comprovante"].name[:200]
            if not obj.usuario_nome:
                obj.usuario_nome = getattr(request.user, "nome", "")
            obj.save()
            messages.success(request, "Saída salva.")
            return _voltar(request)
        return _render(request, despesa_form=form, editando=despesa, aba="saidas")
    return _render(request, editando=despesa, aba="saidas")


@admin_required
def despesa_excluir(request, pk):
    despesa = get_object_or_404(Despesa, pk=pk)
    if request.method == "POST":
        if despesa.comprovante:
            despesa.comprovante.delete(save=False)
        despesa.delete()
        messages.success(request, "Saída excluída.")
    return _voltar(request)


@admin_required
def comprovante(request, pk):
    despesa = get_object_or_404(Despesa, pk=pk)
    if not despesa.comprovante:
        raise Http404("Sem comprovante.")
    try:
        arquivo = despesa.comprovante.open("rb")
    except OSError:
        raise Http404("Arquivo não encontrado.")
    return FileResponse(arquivo, filename=despesa.comprovante_nome or "comprovante", as_attachment=False)


@admin_required
def reposicao_alternar(request):
    """"Não é compra" / "Contar de novo" numa linha de reposição de estoque."""
    if request.method == "POST":
        movimentos = caixa.movimentos_reposicao(request.POST.get("chave", ""))
        contar = request.POST.get("contar") == "1"
        alterados = movimentos.update(fora_do_financeiro=not contar)
        if alterados:
            messages.success(request, "Reposição volta a contar como saída." if contar else "Reposição tirada das saídas.")
    return _voltar(request)
