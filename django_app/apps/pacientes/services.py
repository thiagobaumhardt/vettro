"""Orquestração de Anamnese/Cirurgia — combina apps.financeiro.services
(precificação) com apps.estoque.services (débito de estoque) e cria a
Cobrança automática, exatamente como backend/app/routers/anamnese.py e
cirurgias.py faziam (§9 do plano)."""
from decimal import Decimal

from django.db import transaction

from apps.estoque.services import debitar_para_consumo
from apps.financeiro import services as financeiro_services
from apps.financeiro.models import CirurgiaCategoria

from .models import AnamneseHist, CirurgiaHist


@transaction.atomic
def criar_anamnese(*, paciente, dados_clinicos: dict, servico_ids, usos_insumos, plantao: bool, usuario) -> AnamneseHist:
    servicos_itens, total_servicos = financeiro_services.montar_servicos(servico_ids)
    insumos_itens, total_insumos, debitos = financeiro_services.montar_insumos(usos_insumos)

    total = total_servicos + total_insumos
    servicos_para_cobranca = list(servicos_itens)
    if plantao:
        acrescimo, item_plantao = financeiro_services.aplicar_plantao(total_servicos)
        total += acrescimo
        if item_plantao:
            servicos_para_cobranca.append(item_plantao)

    anamnese = AnamneseHist.objects.create(
        paciente=paciente, servicos=servicos_itens, insumos=insumos_itens,
        plantao=plantao, total=total, **dados_clinicos,
    )

    for insumo, qtd in debitos:
        debitar_para_consumo(
            insumo=insumo, quantidade=qtd, subtipo="consumo_atendimento",
            origem_tipo="anamnese", origem_id=anamnese.id, usuario=usuario,
        )

    financeiro_services.criar_cobranca_automatica(
        paciente=paciente, servicos_itens=servicos_para_cobranca, insumos_itens=insumos_itens,
        total=total, obs=f"Anamnese de {anamnese.data:%d/%m/%Y}",
    )
    return anamnese


@transaction.atomic
def criar_cirurgia(*, paciente, dados: dict, categoria_ids, usos_insumos, plantao: bool, outra_cidade: bool, usuario) -> CirurgiaHist:
    procedimentos_itens = []
    total_proc = Decimal("0")
    for categoria_id in categoria_ids:
        categoria = CirurgiaCategoria.objects.get(pk=categoria_id)
        valor = financeiro_services.valor_por_peso(categoria, paciente.peso)
        procedimentos_itens.append({"id": str(categoria.id), "nome": categoria.nome, "valor": str(valor)})
        total_proc += valor

    insumos_itens, total_insumos, debitos = financeiro_services.montar_insumos(usos_insumos)

    total = total_proc + total_insumos
    procedimentos_para_cobranca = list(procedimentos_itens)
    if plantao:
        acrescimo, item_plantao = financeiro_services.aplicar_plantao(total_proc)
        total += acrescimo
        if item_plantao:
            procedimentos_para_cobranca.append(item_plantao)
    if outra_cidade:
        valor_desloc, item_desloc = financeiro_services.aplicar_outra_cidade()
        total += valor_desloc
        procedimentos_para_cobranca.append(item_desloc)

    cirurgia = CirurgiaHist.objects.create(
        paciente=paciente, procedimentos=procedimentos_itens, insumos=insumos_itens,
        plantao=plantao, outra_cidade=outra_cidade, total=total, **dados,
    )

    for insumo, qtd in debitos:
        debitar_para_consumo(
            insumo=insumo, quantidade=qtd, subtipo="consumo_atendimento",
            origem_tipo="cirurgia", origem_id=cirurgia.id, usuario=usuario,
        )

    financeiro_services.criar_cobranca_automatica(
        paciente=paciente, servicos_itens=procedimentos_para_cobranca, insumos_itens=insumos_itens,
        total=total, obs=f"Cirurgia: {cirurgia.proc}",
    )
    return cirurgia


def usos_insumos_do_post(post) -> list[dict]:
    """Lê os checkboxes `insumo_ids` + inputs `qtd_<id>` do POST — mesmo
    padrão usado em Anamnese/Cirurgia/Atendimentos."""
    usos = []
    for insumo_id in post.getlist("insumo_ids"):
        qtd_bruta = post.get(f"qtd_{insumo_id}", "1")
        try:
            qtd = max(1, int(qtd_bruta))
        except ValueError:
            qtd = 1
        usos.append({"insumo_id": insumo_id, "qtd": qtd})
    return usos
