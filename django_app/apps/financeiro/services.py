"""Regras de negócio de precificação — porte de backend/app/utils.py
(montar_servicos/montar_insumos/valor_por_peso) e das constantes de plantão/
outra_cidade do backend/app/routers/anamnese.py e cirurgias.py (§9 do plano)."""
from decimal import Decimal, InvalidOperation

from django.conf import settings

from apps.estoque.models import Insumo

from .models import Cobranca, Servico


class ItemNaoEncontradoError(Exception):
    pass


def _qtd(valor) -> Decimal:
    try:
        qtd = Decimal(str(valor).replace(",", "."))
    except InvalidOperation as exc:
        raise ItemNaoEncontradoError(f"Quantidade inválida: {valor}.") from exc
    if qtd <= 0:
        raise ItemNaoEncontradoError("A quantidade precisa ser maior que zero.")
    return qtd


def _dinheiro(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("0.01"))


def montar_servicos(usos) -> tuple[list[dict], Decimal]:
    """Resolve Servicos em snapshot denormalizado (§3 do plano — cópia
    ponto-no-tempo, não FK, pra não mudar o histórico se o preço do catálogo
    mudar depois) + total. `usos` = [{"servico_id", "qtd"}] (qtd decimal pra
    serviço por tempo: 1,5 hora de oxigênio) — aceita também uma lista de
    ids, que vale quantidade 1."""
    itens = []
    total = Decimal("0")
    for uso in usos:
        servico_id, qtd = (uso["servico_id"], _qtd(uso["qtd"])) if isinstance(uso, dict) else (uso, Decimal("1"))
        try:
            servico = Servico.objects.get(pk=servico_id)
        except Servico.DoesNotExist as exc:
            raise ItemNaoEncontradoError(f"Serviço {servico_id} não encontrado.") from exc
        subtotal = _dinheiro(servico.valor * qtd)
        itens.append({
            "id": str(servico.id), "nome": servico.nome, "valor": str(servico.valor),
            "qtd": f"{qtd.normalize():f}", "unidade": servico.unidade_cobranca, "subtotal": str(subtotal),
        })
        total += subtotal
    return itens, total


def servicos_do_post(post) -> list[dict]:
    """Checkboxes `servico_ids` + inputs `qtd_servico_<id>` (padrão 1)."""
    return [
        {"servico_id": sid, "qtd": post.get(f"qtd_servico_{sid}") or "1"}
        for sid in post.getlist("servico_ids")
    ]


def montar_insumos(usos: list[dict]) -> tuple[list[dict], Decimal, list[tuple[Insumo, Decimal]]]:
    """`usos` = [{"insumo_id": ..., "qtd": ...}, ...] com qtd na UNIDADE DE
    USO do insumo (pode ser fração: 2,5 ml). Retorna snapshot + total +
    lista de (Insumo, qtd) pra o chamador debitar via
    apps.estoque.services.debitar_para_consumo depois de criar o registro
    pai (Anamnese/Cirurgia/Atendimento/Cobrança/Venda), preservando a
    referência de origem no ledger."""
    from apps.estoque.services import EstoqueInsuficienteError

    itens = []
    total = Decimal("0")
    debitos = []
    for uso in usos:
        try:
            insumo = Insumo.objects.get(pk=uso["insumo_id"])
        except Insumo.DoesNotExist as exc:
            raise ItemNaoEncontradoError(f"Insumo {uso['insumo_id']} não encontrado.") from exc

        qtd = _qtd(uso["qtd"])
        if qtd > insumo.qtd:
            raise EstoqueInsuficienteError(insumo.nome, insumo.qtd, qtd, insumo.unidade_rotulo)

        subtotal = _dinheiro(insumo.valor * qtd)
        itens.append({
            "id": str(insumo.id), "nome": insumo.nome, "valor": str(insumo.valor),
            "qtd": f"{qtd.normalize():f}", "unidade": insumo.unidade_rotulo, "subtotal": str(subtotal),
        })
        total += subtotal
        debitos.append((insumo, qtd))

    return itens, total, debitos


def valor_por_peso(categoria, peso) -> Decimal:
    """Faixas de peso: <10kg → P, 10–25kg → M, >25kg → G; sem peso (0/None),
    cai no fallback valor_p or valor_m or valor_g — igual ao FastAPI atual."""
    if peso:
        peso = Decimal(peso)
        if peso < 10:
            valor = categoria.valor_p
        elif peso <= 25:
            valor = categoria.valor_m
        else:
            valor = categoria.valor_g
        if valor is not None:
            return valor
    return categoria.valor_p or categoria.valor_m or categoria.valor_g or Decimal("0")


PLANTAO_LABEL = "Plantão (+50%)"
OUTRA_CIDADE_LABEL = "Deslocamento (outra cidade)"


def aplicar_plantao(total_base: Decimal) -> tuple[Decimal, dict | None]:
    """+50% só sobre o subtotal de serviços/procedimentos — NUNCA sobre
    insumos. Retorna o acréscimo e um item sintético pra exibição na
    Cobrança (não é persistido no registro de Anamnese/Cirurgia em si)."""
    if total_base <= 0:
        return Decimal("0"), None
    acrescimo = total_base * Decimal(str(settings.PLANTAO_ACRESCIMO))
    return acrescimo, {"nome": PLANTAO_LABEL, "valor": str(acrescimo)}


def aplicar_outra_cidade() -> tuple[Decimal, dict]:
    """+R$50 fixo (não percentual), independente e acumulável com plantão."""
    valor = Decimal(str(settings.CIRURGIA_OUTRA_CIDADE_VALOR))
    return valor, {"nome": OUTRA_CIDADE_LABEL, "valor": str(valor)}


def criar_cobranca_automatica(
    *, paciente, servicos_itens, insumos_itens, total, tutor_nome="", obs="", atendimento=None,
) -> Cobranca | None:
    """Anamnese/Cirurgia/Atendimento com itens faturáveis geram Cobrança
    pendente automaticamente. (Atendimento passou a gerar em 2026-09 — antes
    era uma assimetria proposital herdada do sistema antigo.)"""
    if not servicos_itens and not insumos_itens:
        return None
    return Cobranca.objects.create(
        paciente=paciente, servicos=servicos_itens, insumos=insumos_itens,
        total=total, status="pendente",
        tutor_nome=tutor_nome or (paciente.tutor.nome if paciente.tutor else ""),
        obs=obs, atendimento=atendimento,
    )


class PagamentoInvalidoError(Exception):
    pass


def calcular_desconto(total: Decimal, tipo: str, informado: Decimal) -> Decimal:
    """Desconto em R$ a partir do que foi digitado (reais ou percentual)."""
    if informado < 0:
        raise PagamentoInvalidoError("O desconto não pode ser negativo.")
    if tipo == "percentual":
        if informado > 100:
            raise PagamentoInvalidoError("O desconto percentual não pode passar de 100%.")
        desconto = (total * informado / 100).quantize(Decimal("0.01"))
    elif tipo == "valor":
        desconto = informado.quantize(Decimal("0.01"))
    else:
        raise PagamentoInvalidoError("Tipo de desconto inválido.")
    if desconto > total:
        raise PagamentoInvalidoError("O desconto não pode ser maior que o total da cobrança.")
    return desconto


def registrar_pagamento(cobranca: Cobranca, *, desconto_tipo: str, desconto_texto: str, motivo: str, usuario) -> Cobranca:
    """Baixa manual (sem TEF). Desconto é opcional; se houver, o motivo é
    obrigatório — fica registrado quem deu o desconto e por quê."""
    from django.utils import timezone

    if cobranca.status == "pago":
        raise PagamentoInvalidoError("Esta cobrança já está paga.")
    texto = (desconto_texto or "").strip().replace(",", ".")
    try:
        informado = Decimal(texto) if texto else Decimal("0")
    except InvalidOperation as exc:
        raise PagamentoInvalidoError("Valor de desconto inválido.") from exc

    desconto = calcular_desconto(cobranca.total, desconto_tipo or "valor", informado) if informado else Decimal("0")
    motivo = (motivo or "").strip()
    if desconto > 0 and not motivo:
        raise PagamentoInvalidoError("Informe o motivo do desconto.")

    cobranca.desconto_tipo = (desconto_tipo or "valor") if desconto > 0 else ""
    cobranca.desconto_informado = informado if desconto > 0 else None
    cobranca.desconto_valor = desconto
    cobranca.desconto_motivo = motivo if desconto > 0 else ""
    cobranca.valor_pago = cobranca.total - desconto
    cobranca.status = "pago"
    cobranca.pago_em = timezone.now()
    cobranca.pago_por_nome = getattr(usuario, "nome", "")
    cobranca.save()
    return cobranca


def valor_a_pagar_do_tutor(tutor) -> Decimal:
    """Soma das Cobranças pendentes de todos os pacientes do tutor."""
    from django.db.models import Sum

    return Cobranca.objects.filter(paciente__tutor=tutor, status="pendente").aggregate(
        s=Sum("total")
    )["s"] or Decimal("0")
