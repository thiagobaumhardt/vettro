"""Telas de gestão do estoque (estilo SimplesVet): outras saídas, inventário,
análise e etiquetas. Sem fornecedores/pedidos de compra — a clínica compra
avulso (entrada manual ou XML da nota)."""
import json
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.decorators import admin_required, requer_secao

from . import etiquetas, operacoes
from .models import Insumo, Inventario, MotivoSaida, SaidaEstoque
from .services import EstoqueInsuficienteError, insumos_para_busca


def _dec(valor, padrao="0") -> Decimal:
    try:
        return Decimal(str(valor or padrao).replace(",", "."))
    except InvalidOperation:
        return Decimal(padrao)


def _data(valor, padrao):
    try:
        return date.fromisoformat(valor) if valor else padrao
    except ValueError:
        return padrao


def _quem(request) -> str:
    return getattr(request.user, "nome", "") or request.user.get_username()


def _catalogo_json():
    """Produtos pros seletores (saídas, inventário, etiquetas)."""
    return json.dumps([{
        "id": str(i.pk), "nome": i.nome, "codigo": i.codigo_barras or "", "unidade": i.unidade_rotulo,
        "estoque": float(i.qtd), "embalagem": i.embalagem or "emb.", "conteudo": float(i.unidades_por_pacote),
        "categoria": i.categoria or "", "valor": float(i.valor),
    } for i in Insumo.objects.all()])


# --- Outras saídas -----------------------------------------------------------------------------

@requer_secao("estoque")
def saidas(request):
    hoje = timezone.localdate()
    desde = _data(request.GET.get("desde"), hoje.replace(day=1))
    ate = _data(request.GET.get("ate"), hoje)
    lista = SaidaEstoque.objects.filter(data__gte=desde, data__lte=ate).select_related("motivo").prefetch_related("itens__insumo")
    tipo = request.GET.get("tipo", "")
    if tipo:
        lista = lista.filter(tipo=tipo)
    return render(request, "estoque/saidas.html", {
        "saidas": lista, "resumo": operacoes.resumo_saidas(desde, ate), "desde": desde, "ate": ate, "tipo": tipo,
        "tipos": SaidaEstoque.TIPO_CHOICES, "aba": "saidas", "visao": request.GET.get("visao", "lista"),
    })


@requer_secao("estoque")
def saida_nova(request):
    if request.method == "POST":
        itens = []
        for insumo_id in request.POST.getlist("insumo_ids"):
            insumo = Insumo.objects.filter(pk=insumo_id).first()
            qtd = _dec(request.POST.get(f"qtd_{insumo_id}"))
            if insumo and qtd > 0:
                itens.append((insumo, qtd))
        try:
            saida = operacoes.registrar_saida(
                tipo=request.POST.get("tipo", ""), itens=itens, usuario=request.user,
                data=_data(request.POST.get("data"), timezone.localdate()),
                motivo_nome=request.POST.get("motivo", ""),
                beneficiario=request.POST.get("beneficiario", ""), detalhe=request.POST.get("detalhe", ""),
                solicitante=request.POST.get("solicitante", ""),
            )
            messages.success(request, f"{saida.get_tipo_display()} registrada — baixa de {len(itens)} produto(s) no estoque.")
            return redirect("estoque:saidas")
        except (ValueError, EstoqueInsuficienteError) as exc:
            messages.error(request, str(exc))
    return render(request, "estoque/saida_form.html", {
        "tipos": SaidaEstoque.TIPO_CHOICES, "motivos": MotivoSaida.objects.all(), "aba": "saidas",
        "hoje": timezone.localdate(),
        "insumos_json": json.dumps(insumos_para_busca(Insumo.objects.all())),
    })


# --- Inventário --------------------------------------------------------------------------------

@requer_secao("estoque")
def inventarios(request):
    if request.method == "POST":
        inv = Inventario.objects.create(
            descricao=request.POST.get("descricao", "").strip() or f"Inventário {timezone.localdate():%d/%m/%Y}",
            categoria=request.POST.get("categoria", "").strip(), criado_por_nome=_quem(request),
        )
        return redirect("estoque:inventario", pk=inv.pk)
    categorias = sorted({c for c in Insumo.objects.values_list("categoria", flat=True) if c})
    return render(request, "estoque/inventarios.html", {
        "inventarios": Inventario.objects.prefetch_related("itens"), "categorias": categorias, "aba": "inventario",
    })


@requer_secao("estoque")
def inventario(request, pk):
    inv = get_object_or_404(Inventario, pk=pk)
    contexto = {"inv": inv, "linhas": operacoes.divergencias(inv), "aba": "inventario",
                "nao_contados": operacoes.nao_contados(inv) if inv.status == "aberto" else []}
    if request.headers.get("HX-Request"):
        return render(request, "estoque/_inventario_itens.html", contexto)
    contexto["catalogo_json"] = _catalogo_json()
    return render(request, "estoque/inventario.html", contexto)


@requer_secao("estoque")
def inventario_contar(request, pk):
    """Leitura do código de barras (soma 1) ou quantidade digitada (define). Responde a lista atualizada."""
    inv = get_object_or_404(Inventario, pk=pk)
    erro = None
    if request.method == "POST":
        codigo = request.POST.get("codigo", "").strip()
        insumo = (Insumo.objects.filter(codigo_barras=codigo).first() if codigo else None) or \
            Insumo.objects.filter(pk=request.POST.get("insumo") or None).first()
        if not insumo:
            erro = f"Código {codigo} não encontrado no cadastro." if codigo else "Escolha um produto."
        else:
            somar = request.POST.get("modo", "somar") == "somar"
            qtd = _dec(request.POST.get("quantidade"), "1") if not somar or request.POST.get("quantidade") else Decimal("1")
            validade = request.POST.get("validade") or None
            try:
                operacoes.contar(inv, insumo, quantidade=qtd, somar=somar, validade=validade)
            except ValueError as exc:
                erro = str(exc)
    return render(request, "estoque/_inventario_itens.html", {
        "inv": inv, "linhas": operacoes.divergencias(inv), "erro": erro,
        "nao_contados": operacoes.nao_contados(inv) if inv.status == "aberto" else [],
    })


@requer_secao("estoque")
def inventario_finalizar(request, pk):
    inv = get_object_or_404(Inventario, pk=pk)
    if request.method == "POST":
        if request.POST.get("acao") == "cancelar" and inv.status == "aberto":
            inv.status = "cancelado"
            inv.save(update_fields=["status"])
            messages.success(request, "Inventário cancelado — nada foi ajustado.")
        else:
            try:
                r = operacoes.finalizar(inv, request.user)
                messages.success(request, f"Inventário finalizado: {r['ajustados']} produto(s) ajustado(s), "
                                          f"{r['validades']} validade(s) atualizada(s).")
            except ValueError as exc:
                messages.error(request, str(exc))
    return redirect("estoque:inventario", pk=pk)


# --- Análise ----------------------------------------------------------------------------------

@admin_required
@requer_secao("estoque")
def analise(request):
    dados = operacoes.analise_estoque()
    return render(request, "estoque/analise.html", {
        **dados, "aba": "analise", "visao": request.GET.get("visao", "repor"),
    })


# --- Etiquetas --------------------------------------------------------------------------------

@requer_secao("estoque")
def etiquetas_view(request):
    if request.method == "POST":
        pedidos = []
        for insumo_id in request.POST.getlist("insumo_ids"):
            insumo = Insumo.objects.filter(pk=insumo_id).first()
            qtd = int(_dec(request.POST.get(f"qtd_{insumo_id}"), "1"))
            if insumo and qtd > 0:
                etiquetas.garantir_codigo(insumo)
                pedidos.append((insumo, min(qtd, 500)))
        conteudo = etiquetas.gerar_pdf(pedidos, request.POST.get("modelo", "6080"), int(_dec(request.POST.get("pular"), "0")))
        resposta = HttpResponse(conteudo, content_type="application/pdf")
        resposta["Content-Disposition"] = 'inline; filename="etiquetas.pdf"'
        return resposta

    # Pré-seleção: produtos marcados na lista.
    iniciais = {}
    for insumo_id in request.GET.getlist("insumo"):
        iniciais.setdefault(insumo_id, 1)
    return render(request, "estoque/etiquetas.html", {
        "modelos": etiquetas.MODELOS, "aba": "etiquetas",
        "insumos_json": json.dumps(insumos_para_busca(Insumo.objects.all())), "iniciais_json": json.dumps(iniciais),
    })
