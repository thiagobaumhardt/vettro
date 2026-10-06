import json
from datetime import date

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.clickjacking import xframe_options_sameorigin

from apps.core.decorators import admin_required, requer_secao
from apps.estoque.models import Insumo
from apps.estoque.services import EstoqueInsuficienteError
from apps.financeiro.services import ItemNaoEncontradoError

from . import services
from .models import Venda


@requer_secao("vendas")
def lista(request):
    vendas = Venda.objects.all()
    de, ate = request.GET.get("de", ""), request.GET.get("ate", "")
    if de:
        vendas = vendas.filter(criado_em__date__gte=de)
    if ate:
        vendas = vendas.filter(criado_em__date__lte=ate)
    termo = request.GET.get("q", "").strip()
    if termo:
        filtro = Q(cliente_nome__icontains=termo)
        if termo.lstrip("#").isdigit():
            filtro |= Q(numero=int(termo.lstrip("#")))
        vendas = vendas.filter(filtro)

    validas = vendas.filter(cancelada_em__isnull=True)
    resumo = validas.aggregate(qtd=Count("id"), total=Sum("total"), descontos=Sum("desconto_valor"))
    hoje = Venda.objects.filter(cancelada_em__isnull=True, criado_em__date=date.today()).aggregate(qtd=Count("id"), total=Sum("total"))
    return render(request, "vendas/lista.html", {
        "pagina": Paginator(vendas, 50).get_page(request.GET.get("pagina")),
        "filtros": request.GET, "resumo": resumo, "hoje": hoje,
    })


def _renderizar_form(request, estado):
    produtos = Insumo.objects.filter(qtd__gt=0).order_by("nome")
    return render(request, "vendas/form.html", {
        "formas": Venda.FORMA_PAGAMENTO_CHOICES,
        "produtos_json": json.dumps([
            {"id": str(p.id), "nome": p.nome, "valor": str(p.valor), "estoque": float(p.qtd),
             "unidade": p.unidade_rotulo, "codigo": p.codigo_barras or ""}
            for p in produtos
        ]),
        "estado_json": json.dumps(estado),
    })


@requer_secao("vendas")
def nova(request):
    if request.method != "POST":
        return _renderizar_form(request, {"itens": [], "forma": "", "tipo": "valor", "desconto": "", "motivo": "", "cliente": ""})

    post = request.POST
    estado = {
        "itens": [{"insumo": i, "qtd": q} for i, q in zip(post.getlist("item_insumo"), post.getlist("item_qtd"))],
        "forma": post.get("forma_pagamento", ""), "tipo": post.get("desconto_tipo", "valor"),
        "desconto": post.get("desconto", ""), "motivo": post.get("desconto_motivo", ""), "cliente": post.get("cliente_nome", ""),
    }
    try:
        venda = services.registrar_venda(
            usos=services.usos_do_post(post), forma_pagamento=estado["forma"],
            desconto_tipo=estado["tipo"], desconto_texto=estado["desconto"], motivo=estado["motivo"],
            cliente_nome=estado["cliente"], usuario=request.user,
        )
    except (services.VendaInvalidaError, EstoqueInsuficienteError, ItemNaoEncontradoError) as exc:
        messages.error(request, str(exc))
        return _renderizar_form(request, estado)
    messages.success(request, f"Venda #{venda.numero} registrada — R$ {venda.total}. Estoque atualizado.")
    from apps.pagamentos.notas import emitir

    nota = emitir(venda=venda, clinica_nome=request.session.get("clinica_nome", ""), usuario=request.user)
    if nota.status != "emitida":
        messages.warning(request, f"A nota de venda não foi autorizada: {nota.mensagem_erro}")
    return redirect("vendas:detalhe", pk=venda.pk)


@requer_secao("vendas")
def detalhe(request, pk):
    venda = get_object_or_404(Venda, pk=pk)
    return render(request, "vendas/detalhe.html", {"venda": venda, "nota": venda.notas_fiscais.order_by("-criado_em").first()})


@xframe_options_sameorigin  # pré-visualização em <iframe> na tela de detalhe
@requer_secao("vendas")
def comprovante(request, pk):
    venda = get_object_or_404(Venda, pk=pk)
    conteudo = services.pdf_comprovante(venda, clinica_nome=request.session.get("clinica_nome", ""))
    resposta = HttpResponse(conteudo, content_type="application/pdf")
    resposta["Content-Disposition"] = f'inline; filename="comprovante-venda-{venda.numero}.pdf"'
    return resposta


@admin_required
def cancelar(request, pk):
    if request.method == "POST":
        venda = get_object_or_404(Venda, pk=pk)
        try:
            services.cancelar_venda(venda, usuario=request.user)
            messages.success(request, f"Venda #{venda.numero} cancelada. Produtos devolvidos ao estoque.")
        except services.VendaInvalidaError as exc:
            messages.error(request, str(exc))
    return redirect("vendas:lista")
