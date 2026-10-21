import json
from datetime import date

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin

from apps.core.decorators import requer_secao
from apps.estoque.models import Insumo
from apps.estoque.services import EstoqueInsuficienteError
from apps.financeiro.services import ItemNaoEncontradoError
from apps.pagamentos.services import TEFError, cancelar_tef, iniciar_tef_venda

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
        filtro = Q(cliente_nome__icontains=termo) | Q(cliente_cpf__icontains=termo)
        if termo.lstrip("#").isdigit():
            filtro |= Q(numero=int(termo.lstrip("#")))
        vendas = vendas.filter(filtro)

    validas = vendas.filter(cancelada_em__isnull=True, pagamento_status="pago")
    resumo = validas.aggregate(qtd=Count("id"), total=Sum("total"), descontos=Sum("desconto_valor"))
    lucros = [v.lucro for v in validas]
    lucro = {"valor": sum((l for l in lucros if l is not None), 0), "sem_custo": sum(1 for l in lucros if l is None)}
    hoje = Venda.objects.filter(cancelada_em__isnull=True, pagamento_status="pago", criado_em__date=date.today()).aggregate(qtd=Count("id"), total=Sum("total"))
    return render(request, "vendas/lista.html", {
        "pagina": Paginator(vendas, 50).get_page(request.GET.get("pagina")),
        "filtros": request.GET, "resumo": resumo, "hoje": hoje, "lucro": lucro,
    })


def _renderizar_form(request, estado):
    produtos = Insumo.objects.para_venda().filter(qtd__gt=0).order_by("nome")
    return render(request, "vendas/form.html", {
        "formas": Venda.FORMA_PAGAMENTO_CHOICES, "max_parcelas": range(1, services.MAX_PARCELAS + 1),
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
        return _renderizar_form(request, {"itens": [], "forma": "", "parcelas": 1, "tipo": "valor", "desconto": "", "motivo": "", "cliente": "", "cpf": ""})

    post = request.POST
    estado = {
        "itens": [{"insumo": i, "qtd": q} for i, q in zip(post.getlist("item_insumo"), post.getlist("item_qtd"))],
        "forma": post.get("forma_pagamento", ""), "parcelas": post.get("parcelas", "1"), "tipo": post.get("desconto_tipo", "valor"),
        "desconto": post.get("desconto", ""), "motivo": post.get("desconto_motivo", ""), "cliente": post.get("cliente_nome", ""),
        "cpf": post.get("cliente_cpf", ""),
    }
    try:
        venda = services.registrar_venda(
            usos=services.usos_do_post(post), forma_pagamento=estado["forma"],
            desconto_tipo=estado["tipo"], desconto_texto=estado["desconto"], motivo=estado["motivo"],
            cliente_nome=estado["cliente"], cliente_cpf=estado["cpf"], parcelas=estado["parcelas"], usuario=request.user,
        )
    except (services.VendaInvalidaError, EstoqueInsuficienteError, ItemNaoEncontradoError) as exc:
        messages.error(request, str(exc))
        return _renderizar_form(request, estado)
    if venda.aguardando_pagamento:
        _cobrar_na_maquininha(request, venda)
        return redirect("vendas:pagamento", pk=venda.pk)
    messages.success(request, f"Venda #{venda.numero} registrada — R$ {venda.total}. Estoque atualizado.")
    _emitir_nota(request, venda)
    return redirect("vendas:detalhe", pk=venda.pk)


def _emitir_nota(request, venda):
    from apps.pagamentos.notas import emitir

    nota = emitir(venda=venda, clinica_nome=request.session.get("clinica_nome", ""), usuario=request.user)
    if nota.status != "emitida":
        messages.warning(request, f"A nota de venda não foi autorizada: {nota.mensagem_erro}")


def _cobrar_na_maquininha(request, venda):
    try:
        transacao = iniciar_tef_venda(venda, usuario=request.user)
    except TEFError as exc:
        messages.error(request, str(exc))
        return
    if transacao.status == "erro":
        messages.error(request, transacao.mensagem_erro or "Erro ao falar com a maquininha.")


def _contexto_pagamento(venda):
    return {
        "venda": venda, "transacao": venda.transacoes_tef.order_by("-criado_em").first(),
        "formas": Venda.FORMA_PAGAMENTO_CHOICES, "max_parcelas": range(1, services.MAX_PARCELAS + 1),
    }


@requer_secao("vendas")
def pagamento(request, pk):
    """Tela "aguardando maquininha": consulta sozinha (HTMX) até aprovar,
    negar ou o operador cancelar/trocar a forma de pagamento."""
    venda = get_object_or_404(Venda, pk=pk)
    if not venda.aguardando_pagamento:
        return redirect("vendas:detalhe", pk=venda.pk)
    return render(request, "vendas/pagamento.html", _contexto_pagamento(venda))


@requer_secao("vendas")
def pagamento_status(request, pk):
    venda = services.atualizar_pagamento(get_object_or_404(Venda, pk=pk))
    if not venda.aguardando_pagamento:
        if venda.pagamento_status == "pago":
            messages.success(request, f"Pagamento aprovado — venda #{venda.numero}, R$ {venda.total}.")
            _emitir_nota(request, venda)
        resposta = HttpResponse()
        resposta["HX-Redirect"] = reverse("vendas:detalhe", args=[venda.pk])
        return resposta
    return render(request, "vendas/_pagamento_status.html", _contexto_pagamento(venda))


@requer_secao("vendas")
def pagamento_cobrar(request, pk):
    """Manda de novo pra maquininha (depois de recusa/erro/cancelamento)."""
    venda = get_object_or_404(Venda, pk=pk)
    if request.method == "POST":
        _cobrar_na_maquininha(request, venda)
    return redirect("vendas:pagamento", pk=venda.pk)


@requer_secao("vendas")
def pagamento_cancelar(request, pk):
    """Tira a cobrança da maquininha (cliente desistiu, valor errado...). A
    venda continua aguardando — dá pra cobrar de novo ou trocar a forma."""
    venda = get_object_or_404(Venda, pk=pk)
    if request.method == "POST":
        transacao = venda.transacoes_tef.filter(status="pendente").first()
        if transacao:
            try:
                cancelar_tef(transacao)
            except TEFError as exc:
                messages.error(request, str(exc))
    return redirect("vendas:pagamento", pk=venda.pk)


@requer_secao("vendas")
def pagamento_trocar(request, pk):
    venda = get_object_or_404(Venda, pk=pk)
    if request.method != "POST":
        return redirect("vendas:pagamento", pk=venda.pk)
    try:
        services.trocar_forma_pagamento(venda, forma=request.POST.get("forma_pagamento", ""), parcelas=request.POST.get("parcelas"))
    except services.VendaInvalidaError as exc:
        messages.error(request, str(exc))
        return redirect("vendas:pagamento", pk=venda.pk)
    if venda.aguardando_pagamento:
        _cobrar_na_maquininha(request, venda)
        return redirect("vendas:pagamento", pk=venda.pk)
    messages.success(request, f"Venda #{venda.numero} paga em {venda.get_forma_pagamento_display().lower()}.")
    _emitir_nota(request, venda)
    return redirect("vendas:detalhe", pk=venda.pk)


@requer_secao("vendas")
def buscar_cpf(request):
    """Balcão: o cliente deu o CPF — já é tutor cadastrado?"""
    from apps.core.validators import cpf_valido

    cpf = request.GET.get("cpf", "")
    if not cpf_valido(cpf):
        return JsonResponse({"valido": False})
    tutor = services.tutor_por_cpf(cpf)
    return JsonResponse({"valido": True, "tutor": {"id": str(tutor.pk), "nome": tutor.nome} if tutor else None})


@requer_secao("vendas")
def detalhe(request, pk):
    venda = get_object_or_404(Venda, pk=pk)
    if venda.aguardando_pagamento:
        return redirect("vendas:pagamento", pk=venda.pk)
    return render(request, "vendas/detalhe.html", {"venda": venda, "nota": venda.notas_fiscais.order_by("-criado_em").first()})


@xframe_options_sameorigin  # pré-visualização em <iframe> na tela de detalhe
@requer_secao("vendas")
def comprovante(request, pk):
    venda = get_object_or_404(Venda, pk=pk)
    conteudo = services.pdf_comprovante(venda, clinica_nome=request.session.get("clinica_nome", ""))
    resposta = HttpResponse(conteudo, content_type="application/pdf")
    resposta["Content-Disposition"] = f'inline; filename="comprovante-venda-{venda.numero}.pdf"'
    return resposta


@requer_secao("vendas")
def cancelar(request, pk):
    """Admin cancela qualquer venda; quem vende só desiste de uma que ainda
    não foi paga (aguardando maquininha)."""
    if request.method == "POST":
        venda = get_object_or_404(Venda, pk=pk)
        if request.session.get("papel") != "admin" and not venda.aguardando_pagamento:
            raise PermissionDenied("Só o admin cancela venda já paga.")
        try:
            services.cancelar_venda(venda, usuario=request.user)
            messages.success(request, f"Venda #{venda.numero} cancelada. Produtos devolvidos ao estoque.")
        except services.VendaInvalidaError as exc:
            messages.error(request, str(exc))
    return redirect("vendas:lista")
