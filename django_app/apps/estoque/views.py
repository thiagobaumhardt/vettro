from django.contrib import messages
from django.db.models import ProtectedError, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import requer_secao

from . import services
from .forms import AjusteForm, EntradaManualForm, InsumoForm
from .models import Insumo
from .nfe import NFeInvalidaError


@requer_secao("estoque")
def lista(request):
    termo = request.GET.get("q", "").strip()
    insumos = Insumo.objects.all()
    if termo:
        insumos = insumos.filter(Q(nome__icontains=termo) | Q(categoria__icontains=termo))

    contexto = {"insumos": insumos, "termo": termo, "alertas": services.alertas_estoque()}
    template = "estoque/_lista_resultado.html" if request.headers.get("HX-Request") else "estoque/lista.html"
    return render(request, template, contexto)


@requer_secao("estoque")
def form_view(request, pk=None):
    insumo = get_object_or_404(Insumo, pk=pk) if pk else None

    if request.method == "POST":
        form = InsumoForm(request.POST, instance=insumo)
        if form.is_valid():
            form.save()
            messages.success(request, "Insumo salvo com sucesso.")
            return redirect("estoque:lista")
    else:
        form = InsumoForm(instance=insumo)

    return render(request, "estoque/form.html", {"form": form, "insumo": insumo})


@requer_secao("estoque")
def excluir(request, pk):
    insumo = get_object_or_404(Insumo, pk=pk)
    if request.method == "POST":
        try:
            insumo.delete()
            messages.success(request, "Insumo excluído.")
        except ProtectedError:
            messages.error(request, "Esse insumo já tem movimentações de estoque registradas e não pode ser excluído.")
        return redirect("estoque:lista")
    return redirect("estoque:lista")


@requer_secao("estoque")
def codigo_lookup(request, codigo):
    insumo = Insumo.objects.filter(codigo_barras=codigo).first()
    if insumo:
        return render(request, "estoque/_scan_encontrado.html", {"insumo": insumo})
    return render(request, "estoque/_scan_nao_encontrado.html", {"codigo": codigo})


@requer_secao("estoque")
def entrada_manual(request):
    insumo_inicial = request.GET.get("insumo")

    if request.method == "POST":
        form = EntradaManualForm(request.POST)
        if form.is_valid():
            services.entrada_manual(
                insumo=form.cleaned_data["insumo"],
                quantidade=form.cleaned_data["quantidade"],
                valor_unitario=form.cleaned_data["valor_unitario"] or form.cleaned_data["insumo"].valor,
                lote=form.cleaned_data["lote"],
                data_validade=form.cleaned_data["data_validade"],
                observacao=form.cleaned_data["observacao"],
                usuario=request.user,
            )
            messages.success(request, "Entrada registrada no estoque.")
            return redirect("estoque:lista")
    else:
        form = EntradaManualForm(initial={"insumo": insumo_inicial} if insumo_inicial else None)

    return render(request, "estoque/entrada_manual.html", {"form": form})


@requer_secao("estoque")
def importar_xml(request):
    if request.method == "POST" and request.FILES.get("arquivo"):
        try:
            resultado = services.importar_nfe(request.FILES["arquivo"].read(), request.user)
            messages.success(
                request,
                f"Importação concluída: {resultado['criados']} criado(s), "
                f"{resultado['atualizados']} atualizado(s), {resultado['ignorados']} ignorado(s).",
            )
        except NFeInvalidaError as exc:
            messages.error(request, str(exc))
        return redirect("estoque:lista")
    return redirect("estoque:lista")


@requer_secao("estoque")
def ajustar(request, pk):
    insumo = get_object_or_404(Insumo, pk=pk)
    if request.method == "POST":
        form = AjusteForm(request.POST)
        if form.is_valid():
            services.ajustar_estoque(
                insumo=insumo, quantidade=form.cleaned_data["quantidade"],
                positivo=form.cleaned_data["sinal"] == "positivo",
                motivo=form.cleaned_data["motivo"], usuario=request.user,
            )
            messages.success(request, "Ajuste de estoque registrado.")
    return redirect("estoque:lista")


@requer_secao("estoque")
def movimentos(request, pk):
    insumo = get_object_or_404(Insumo, pk=pk)
    return render(request, "estoque/_movimentos.html", {"insumo": insumo, "movimentos": insumo.movimentos.all()[:50]})
