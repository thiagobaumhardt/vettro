import json
from decimal import Decimal

from django.contrib import messages
from django.db.models import ProtectedError, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import admin_required, requer_secao

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


@admin_required  # cadastrar/editar insumo é só do admin da clínica
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

    from apps.core.models import ConfiguracaoClinica

    from .fiscal import tributacao_de_venda

    tributacao = tributacao_de_venda(insumo, ConfiguracaoClinica.atual()) if insumo else None
    return render(request, "estoque/form.html", {"form": form, "insumo": insumo, "tributacao": tributacao})


@admin_required
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
            dados = form.cleaned_data
            insumo = dados["insumo"]
            em_embalagens = dados["lancar_em"] == "embalagem"
            qtd_uso = services.para_unidade_de_uso(insumo, dados["quantidade"], em_embalagens)
            # Custo guardado sempre por unidade de uso.
            if dados["valor_unitario"] is not None:
                custo = dados["valor_unitario"] / insumo.unidades_por_pacote if em_embalagens else dados["valor_unitario"]
            else:
                custo = insumo.valor
            descricao = (
                f"{services.formatar_qtd(dados['quantidade'])} {insumo.embalagem or 'embalagem'}(s) = "
                if em_embalagens else ""
            ) + f"{services.formatar_qtd(qtd_uso)} {insumo.unidade_rotulo}"
            services.entrada_manual(
                insumo=insumo, quantidade=qtd_uso, valor_unitario=custo.quantize(Decimal("0.0001")),
                lote=dados["lote"], data_validade=dados["data_validade"],
                observacao=dados["observacao"] or f"Entrada manual sem nota: {descricao}",
                usuario=request.user,
            )
            messages.success(request, f"Entrada registrada: {descricao} de {insumo.nome}.")
            return redirect("estoque:lista")
    else:
        form = EntradaManualForm(initial={"insumo": insumo_inicial} if insumo_inicial else None)

    produtos = {
        str(i.pk): {"unidade": i.unidade_rotulo, "embalagem": i.embalagem or "embalagem", "conteudo": str(i.unidades_por_pacote)}
        for i in Insumo.objects.all()
    }
    return render(request, "estoque/entrada_manual.html", {
        "form": form, "produtos_json": json.dumps(produtos),
        "insumo_inicial": str(form["insumo"].value() or ""), "lancar_em_inicial": form["lancar_em"].value() or "embalagem",
    })


@admin_required  # cria insumos novos a partir da nota
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
            if resultado["revisar"]:
                nomes = ", ".join(i.nome for i in resultado["revisar"][:5])
                messages.warning(
                    request,
                    f"Confira quantas unidades vêm em cada embalagem de: {nomes}. Entraram como 1 por embalagem.",
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
