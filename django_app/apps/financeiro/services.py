"""Regras de negócio de precificação — porte de backend/app/utils.py
(montar_servicos/montar_insumos/valor_por_peso) e das constantes de plantão/
outra_cidade do backend/app/routers/anamnese.py e cirurgias.py (§9 do plano)."""
from decimal import Decimal

from django.conf import settings

from apps.estoque.models import Insumo

from .models import Cobranca, Servico


class ItemNaoEncontradoError(Exception):
    pass


def montar_servicos(servico_ids: list[str]) -> tuple[list[dict], Decimal]:
    """Resolve ids de Servico em snapshot denormalizado (§3 do plano — cópia
    ponto-no-tempo, não FK, pra não mudar o histórico se o preço do catálogo
    mudar depois) + total."""
    itens = []
    total = Decimal("0")
    for servico_id in servico_ids:
        try:
            servico = Servico.objects.get(pk=servico_id)
        except Servico.DoesNotExist as exc:
            raise ItemNaoEncontradoError(f"Serviço {servico_id} não encontrado.") from exc
        itens.append({"id": str(servico.id), "nome": servico.nome, "valor": str(servico.valor)})
        total += servico.valor
    return itens, total


def montar_insumos(usos: list[dict]) -> tuple[list[dict], Decimal, list[tuple[Insumo, int]]]:
    """`usos` = [{"insumo_id": ..., "qtd": ...}, ...]. Retorna snapshot +
    total + lista de (Insumo, qtd) pra o chamador debitar via
    apps.estoque.services.debitar_para_consumo depois de criar o registro
    pai (Anamnese/Cirurgia/Atendimento/Cobrança), preservando a referência
    de origem no ledger."""
    from apps.estoque.services import EstoqueInsuficienteError

    itens = []
    total = Decimal("0")
    debitos = []
    for uso in usos:
        try:
            insumo = Insumo.objects.get(pk=uso["insumo_id"])
        except Insumo.DoesNotExist as exc:
            raise ItemNaoEncontradoError(f"Insumo {uso['insumo_id']} não encontrado.") from exc

        qtd = int(uso["qtd"])
        if qtd > insumo.qtd:
            raise EstoqueInsuficienteError(insumo.nome, insumo.qtd, qtd)

        itens.append({"id": str(insumo.id), "nome": insumo.nome, "valor": str(insumo.valor), "qtd": qtd})
        total += insumo.valor * qtd
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


PLANTAO_LABEL = "🌙 Plantão (+50%)"
OUTRA_CIDADE_LABEL = "📍 Deslocamento (outra cidade)"


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


def criar_cobranca_automatica(*, paciente, servicos_itens, insumos_itens, total, tutor_nome="", obs="") -> Cobranca | None:
    """Anamnese/Cirurgia com itens faturáveis geram Cobrança pendente
    automaticamente. Atendimento NÃO chama isso — assimetria preservada do
    sistema atual (§9 do plano)."""
    if not servicos_itens and not insumos_itens:
        return None
    return Cobranca.objects.create(
        paciente=paciente, servicos=servicos_itens, insumos=insumos_itens,
        total=total, status="pendente",
        tutor_nome=tutor_nome or (paciente.tutor.nome if paciente.tutor else ""),
        obs=obs,
    )
