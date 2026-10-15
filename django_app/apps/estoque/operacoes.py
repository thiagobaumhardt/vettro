"""Outras saídas, inventário e análise de estoque (estilo SimplesVet). Tudo que
mexe na quantidade passa por services.registrar_movimento (ledger SD1/SD2/SD3)."""
import math
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from .models import (
    Insumo, Inventario, ItemInventario, ItemSaidaEstoque, MotivoSaida, MovimentoEstoque, SaidaEstoque,
)
from .services import EstoqueInsuficienteError, registrar_movimento


# --- Outras saídas -----------------------------------------------------------------------

@transaction.atomic
def registrar_saida(*, tipo: str, itens: list[tuple[Insumo, Decimal]], data: date, usuario, motivo_nome: str = "",
                    beneficiario: str = "", detalhe: str = "", solicitante: str = "") -> SaidaEstoque:
    """Baixa na hora (SD3 do subtipo = tipo). Recusa se faltar estoque."""
    if tipo not in dict(SaidaEstoque.TIPO_CHOICES):
        raise ValueError("Tipo de saída inválido.")
    if not itens:
        raise ValueError("Adicione ao menos um produto.")
    motivo = None
    if motivo_nome.strip():
        motivo, _ = MotivoSaida.objects.get_or_create(nome=motivo_nome.strip()[:100])
    saida = SaidaEstoque.objects.create(
        tipo=tipo, motivo=motivo,
        beneficiario=beneficiario if tipo == "doacao" else "", detalhe=detalhe, solicitante=solicitante,
        data=data, usuario_nome=getattr(usuario, "nome", ""),
    )
    total = Decimal("0")
    for insumo, quantidade in itens:
        atual = Insumo.objects.select_for_update().get(pk=insumo.pk)
        if atual.qtd < quantidade:
            raise EstoqueInsuficienteError(atual.nome, atual.qtd, quantidade, atual.unidade_rotulo)
        custo = atual.custo_referencia
        ItemSaidaEstoque.objects.create(saida=saida, insumo=atual, quantidade=quantidade, custo_unitario=custo)
        registrar_movimento(
            insumo=atual, tipo=MovimentoEstoque.SD3_INTERNO, subtipo=tipo, quantidade=quantidade,
            valor_unitario=custo, origem_tipo="saida_estoque", origem_id=saida.pk,
            observacao=" · ".join(filter(None, [saida.get_tipo_display(), motivo.nome if motivo else "", detalhe]))[:300],
            usuario=usuario,
        )
        total += (quantidade * custo).quantize(Decimal("0.01"))
    saida.total_custo = total
    saida.save(update_fields=["total_custo"])
    return saida


def resumo_saidas(desde: date, ate: date) -> dict:
    """Totais por tipo, motivo, produto e solicitante no período (qtd e custo)."""
    itens = ItemSaidaEstoque.objects.filter(saida__data__gte=desde, saida__data__lte=ate).select_related("saida__motivo", "insumo")
    grupos = {"tipo": {}, "motivo": {}, "produto": {}, "solicitante": {}}
    rotulos_tipo = dict(SaidaEstoque.TIPO_CHOICES)
    total = Decimal("0")
    for item in itens:
        custo = item.custo_total
        total += custo
        chaves = {
            "tipo": rotulos_tipo[item.saida.tipo],
            "motivo": item.saida.motivo.nome if item.saida.motivo else "(sem motivo)",
            "produto": f"{item.insumo.nome} ({item.insumo.unidade_rotulo})",
            "solicitante": item.saida.solicitante or "(não informado)",
        }
        for grupo, chave in chaves.items():
            g = grupos[grupo].setdefault(chave, {"nome": chave, "quantidade": Decimal("0"), "custo": Decimal("0"), "vezes": 0})
            g["quantidade"] += item.quantidade
            g["custo"] += custo
            g["vezes"] += 1
    saida = {}
    for grupo, valores in grupos.items():
        lista = sorted(valores.values(), key=lambda g: g["custo"], reverse=True)
        maior = max((g["custo"] for g in lista), default=Decimal("0")) or Decimal("1")
        for g in lista:
            g["percentual"] = f"{(g['custo'] / maior * 100):.1f}"  # string: largura da barra no CSS
        saida[grupo] = lista
    return {"grupos": saida, "total": total}


# --- Inventário ------------------------------------------------------------------------------

def contar(inventario: Inventario, insumo: Insumo, *, quantidade: Decimal, somar: bool, validade=None) -> ItemInventario:
    """Lança a contagem: `somar=True` acumula (cada leitura do código de barras
    soma 1); senão define o total contado."""
    if inventario.status != "aberto":
        raise ValueError("Este inventário já foi finalizado.")
    item, _ = ItemInventario.objects.get_or_create(inventario=inventario, insumo=insumo)
    item.qtd_contada = (item.qtd_contada + quantidade) if somar else quantidade
    if validade:
        item.validade_contada = validade
    item.save()
    return item


def nao_contados(inventario: Inventario):
    """Produtos do escopo (categoria ou todos) que ainda não foram contados."""
    qs = Insumo.objects.exclude(contagens__inventario=inventario)
    if inventario.categoria:
        qs = qs.filter(categoria__iexact=inventario.categoria)
    return qs.order_by("nome")


def divergencias(inventario: Inventario) -> list[dict]:
    linhas = []
    for item in inventario.itens.select_related("insumo"):
        sistema = item.qtd_sistema if item.qtd_sistema is not None else item.insumo.qtd
        diferenca = item.qtd_contada - sistema
        validade_mudou = bool(item.validade_contada and item.validade_contada != item.insumo.data_validade)
        linhas.append({"item": item, "sistema": sistema, "diferenca": diferenca, "validade_mudou": validade_mudou,
                       "valor": (diferenca * item.insumo.custo_referencia).quantize(Decimal("0.01"))})
    return linhas


@transaction.atomic
def finalizar(inventario: Inventario, usuario) -> dict:
    """Aplica as diferenças (SD3 inventario_positivo/negativo) e as validades
    contadas. Só os produtos contados entram (inventário parcial)."""
    if inventario.status != "aberto":
        raise ValueError("Este inventário já foi finalizado.")
    ajustados = validades = 0
    for item in inventario.itens.select_related("insumo"):
        insumo = Insumo.objects.select_for_update().get(pk=item.insumo_id)
        item.qtd_sistema = insumo.qtd
        item.save(update_fields=["qtd_sistema"])
        diferenca = item.qtd_contada - insumo.qtd
        if diferenca:
            registrar_movimento(
                insumo=insumo, tipo=MovimentoEstoque.SD3_INTERNO,
                subtipo="inventario_positivo" if diferenca > 0 else "inventario_negativo",
                quantidade=abs(diferenca), valor_unitario=insumo.custo_referencia,
                origem_tipo="inventario", origem_id=inventario.pk,
                observacao=f"Inventário: {inventario.descricao}", usuario=usuario,
            )
            ajustados += 1
        if item.validade_contada and item.validade_contada != insumo.data_validade:
            Insumo.objects.filter(pk=insumo.pk).update(data_validade=item.validade_contada)
            validades += 1
    inventario.status = "finalizado"
    inventario.finalizado_em = timezone.now()
    inventario.finalizado_por_nome = getattr(usuario, "nome", "")
    inventario.save()
    return {"ajustados": ajustados, "validades": validades}


# --- Análise de estoque ------------------------------------------------------------------------

JANELA_DIAS = 90
SUBTIPOS_CONSUMO = ("venda_servico", "venda_produto", "consumo_atendimento", "consumo_interno")


def analise_estoque(hoje: date | None = None) -> dict:
    """Sugestão de compra, excedentes, produtos parados (90+ dias sem saída),
    novos produtos e os valores (capital parado, excedente, a repor).

    Consumo = saídas por venda/atendimento/consumo interno nos últimos 90 dias
    (ou desde o cadastro, se mais novo). Estoque ideal = consumo diário ×
    frequência de compras da clínica (compras avulsas, sem fornecedor fixo)."""
    from apps.core.models import ConfiguracaoClinica

    hoje = hoje or timezone.localdate()
    inicio = hoje - timedelta(days=JANELA_DIAS)
    frequencia = ConfiguracaoClinica.atual().estoque_frequencia_compra_dias or 30

    consumo = dict(
        MovimentoEstoque.objects.filter(criado_em__date__gte=inicio, subtipo__in=SUBTIPOS_CONSUMO)
        .filter(Q(tipo=MovimentoEstoque.SD2_SAIDA) | Q(tipo=MovimentoEstoque.SD3_INTERNO))
        .values_list("insumo_id").annotate(total=Sum("quantidade"))
    )
    estornos = dict(
        MovimentoEstoque.objects.filter(criado_em__date__gte=inicio, subtipo="estorno_consumo")
        .values_list("insumo_id").annotate(total=Sum("quantidade"))
    )
    ultima_saida = dict(
        MovimentoEstoque.objects.filter(subtipo__in=SUBTIPOS_CONSUMO).values_list("insumo_id")
        .annotate(ultima=models_max("criado_em"))
    )
    entradas_novos = dict(
        MovimentoEstoque.objects.filter(tipo=MovimentoEstoque.SD1_ENTRADA, criado_em__date__gte=inicio)
        .values_list("insumo_id").annotate(total=Sum("quantidade"))
    )

    repor, excedentes, parados, novos = [], [], [], []
    capital_total = Decimal("0")
    for insumo in Insumo.objects.all():
        custo = insumo.custo_referencia
        capital_total += max(insumo.qtd, Decimal("0")) * custo
        criado = timezone.localtime(insumo.criado_em).date()
        dias = max(1, min(JANELA_DIAS, (hoje - criado).days or 1))
        total_consumo = max(Decimal("0"), (consumo.get(insumo.pk) or Decimal("0")) - (estornos.get(insumo.pk) or Decimal("0")))
        diario = total_consumo / dias
        ideal = diario * frequencia
        if insumo.estoque_minimo is not None:
            ideal = max(ideal, insumo.estoque_minimo)
        cobertura = (insumo.qtd / diario) if diario > 0 else None
        linha = {
            "insumo": insumo, "consumo_90": total_consumo, "diario": diario, "ideal": ideal,
            "cobertura_dias": int(cobertura) if cobertura is not None else None,
        }

        # Repor: abaixo do ideal (com consumo) ou abaixo do mínimo/limite de estoque baixo.
        alvo = ideal if diario > 0 else (insumo.limite_baixo if insumo.qtd < insumo.limite_baixo else Decimal("0"))
        if alvo > insumo.qtd:
            falta = alvo - insumo.qtd
            embalagens = math.ceil(falta / insumo.unidades_por_pacote)
            linha.update(falta=falta, embalagens=embalagens,
                         valor=(Decimal(embalagens) * insumo.unidades_por_pacote * custo).quantize(Decimal("0.01")))
            repor.append(linha)

        if diario > 0 and insumo.qtd > ideal * 2 and insumo.qtd > 0:
            excesso = insumo.qtd - ideal
            excedentes.append({**linha, "excesso": excesso, "valor": (excesso * custo).quantize(Decimal("0.01"))})

        ultima = ultima_saida.get(insumo.pk)
        sem_saida_desde = timezone.localtime(ultima).date() if ultima else criado
        if insumo.qtd > 0 and (hoje - sem_saida_desde).days > JANELA_DIAS:
            parados.append({**linha, "dias_parado": (hoje - sem_saida_desde).days,
                            "valor": (insumo.qtd * custo).quantize(Decimal("0.01"))})

        if (hoje - criado).days <= JANELA_DIAS:
            novos.append({**linha, "criado": criado,
                          "valor": ((entradas_novos.get(insumo.pk) or Decimal("0")) * custo).quantize(Decimal("0.01"))})

    soma = lambda xs: sum((x["valor"] for x in xs), Decimal("0"))  # noqa: E731
    return {
        "repor": sorted(repor, key=lambda x: (x["cobertura_dias"] is None, x["cobertura_dias"] or 0)),
        "excedentes": sorted(excedentes, key=lambda x: x["valor"], reverse=True),
        "parados": sorted(parados, key=lambda x: x["valor"], reverse=True),
        "novos": sorted(novos, key=lambda x: x["criado"], reverse=True),
        "totais": {
            "capital_total": capital_total.quantize(Decimal("0.01")), "a_repor": soma(repor),
            "excedente": soma(excedentes), "parado": soma(parados), "novos": soma(novos),
        },
        "frequencia": frequencia, "janela": JANELA_DIAS,
    }


def models_max(campo):
    from django.db.models import Max

    return Max(campo)
