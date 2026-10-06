from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import admin_required, requer_secao

from .forms import CirurgiaCategoriaForm, ServicoForm
from .models import Cobranca, CirurgiaCategoria, Servico


def _renderizar_catalogo(request, servico_form=None, categoria_form=None, editando_servico=None, editando_categoria=None):
    return render(request, "financeiro/catalogo.html", {
        "servicos": Servico.objects.all(),
        "categorias": CirurgiaCategoria.objects.all(),
        "servico_form": servico_form or ServicoForm(),
        "categoria_form": categoria_form or CirurgiaCategoriaForm(),
        "editando_servico": editando_servico,
        "editando_categoria": editando_categoria,
    })


@requer_secao("financeiro")
def catalogo(request):
    return _renderizar_catalogo(request)


@requer_secao("financeiro")
def servico_salvar(request, pk=None):
    servico = get_object_or_404(Servico, pk=pk) if pk else None
    if request.method == "POST":
        form = ServicoForm(request.POST, instance=servico)
        if form.is_valid():
            form.save()
            messages.success(request, "Serviço salvo.")
            return redirect("financeiro:catalogo")
        return _renderizar_catalogo(request, servico_form=form, editando_servico=servico)
    return _renderizar_catalogo(request, servico_form=ServicoForm(instance=servico), editando_servico=servico)


@requer_secao("financeiro")
def servico_excluir(request, pk):
    if request.method == "POST":
        get_object_or_404(Servico, pk=pk).delete()
        messages.success(request, "Serviço excluído.")
    return redirect("financeiro:catalogo")


@admin_required  # tipos de cirurgia: só o admin da clínica cadastra/edita
@requer_secao("financeiro")
def categoria_salvar(request, pk=None):
    categoria = get_object_or_404(CirurgiaCategoria, pk=pk) if pk else None
    if request.method == "POST":
        form = CirurgiaCategoriaForm(request.POST, instance=categoria)
        if form.is_valid():
            form.save()
            messages.success(request, "Procedimento salvo.")
            return redirect("financeiro:catalogo")
        return _renderizar_catalogo(request, categoria_form=form, editando_categoria=categoria)
    return _renderizar_catalogo(request, categoria_form=CirurgiaCategoriaForm(instance=categoria), editando_categoria=categoria)


@admin_required
@requer_secao("financeiro")
def categoria_excluir(request, pk):
    if request.method == "POST":
        get_object_or_404(CirurgiaCategoria, pk=pk).delete()
        messages.success(request, "Procedimento excluído.")
    return redirect("financeiro:catalogo")


@admin_required
def cobranca_pagar(request, pk):
    """Fase 3: marcar como pago ainda é manual (sem TEF/Focus NFe — isso é
    Fase 6). Ver §13 do plano: esse caminho manual continua existindo mesmo
    depois da Fase 6, como fallback de resiliência."""
    from apps.pacientes.views import _contexto_cobranca

    from .services import PagamentoInvalidoError, registrar_pagamento

    cobranca = get_object_or_404(Cobranca, pk=pk)
    erro = None
    if request.method == "POST":
        try:
            registrar_pagamento(
                cobranca, desconto_tipo=request.POST.get("desconto_tipo", "valor"),
                desconto_texto=request.POST.get("desconto", ""), motivo=request.POST.get("desconto_motivo", ""),
                usuario=request.user,
            )
        except PagamentoInvalidoError as exc:
            erro = str(exc)
        else:
            # Nota de serviço sai automaticamente ao receber; se for recusada
            # (ex.: falta CNPJ), a cobrança mostra o motivo e o botão de tentar de novo.
            from apps.pagamentos.notas import emitir

            emitir(cobranca=cobranca, clinica_nome=request.session.get("clinica_nome", ""), usuario=request.user)
    return render(request, "pacientes/ficha/_ficha_cobranca.html", _contexto_cobranca(cobranca.paciente, erro=erro))
