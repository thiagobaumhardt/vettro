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
    cobranca = get_object_or_404(Cobranca, pk=pk)
    if request.method == "POST":
        cobranca.status = "pago"
        cobranca.save(update_fields=["status"])
        messages.success(request, "Cobrança marcada como paga.")
    return redirect("pacientes:ficha_aba", pk=cobranca.paciente_id, aba="cobranca")
