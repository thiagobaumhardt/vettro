from django.db import connection, transaction
from django.db.models import Max

from apps.estoque.services import debitar_para_consumo, estornar_consumo
from apps.financeiro import services as financeiro_services

from .models import Atendimento


def _proximo_numero() -> int:
    # Lock da tabela (só contra outras escritas) pra dois cadastros simultâneos
    # não pegarem o mesmo número. A tabela é do schema da clínica atual.
    with connection.cursor() as cursor:
        cursor.execute(f"LOCK TABLE {Atendimento._meta.db_table} IN SHARE ROW EXCLUSIVE MODE")
    return (Atendimento.objects.aggregate(m=Max("numero"))["m"] or 0) + 1


def _incluir_insumo_da_vacina(usos_insumos: list[dict], vacina) -> list[dict]:
    """A vacina aplicada sai do estoque (1 unidade) pelo Insumo vinculado —
    a não ser que o vet já tenha marcado esse insumo manualmente na lista."""
    if vacina is None or vacina.insumo_id is None:
        return usos_insumos
    if any(str(uso["insumo_id"]) == str(vacina.insumo_id) for uso in usos_insumos):
        return usos_insumos
    return [*usos_insumos, {"insumo_id": vacina.insumo_id, "qtd": 1}]


@transaction.atomic
def criar_atendimento(
    *, paciente, tipo: str, retorno_de, vacina, dose: str, data_proxima_dose, data_retorno=None, lembrete_dias_antes=None,
    data, hora, servico_ids, usos_insumos, plantao: bool, obs: str, usuario,
) -> Atendimento:
    vacinacao = tipo == Atendimento.Tipo.VACINACAO
    if vacinacao:
        usos_insumos = _incluir_insumo_da_vacina(usos_insumos, vacina)

    servicos_itens, total_servicos = financeiro_services.montar_servicos(servico_ids)
    insumos_itens, total_insumos, debitos = financeiro_services.montar_insumos(usos_insumos)

    total = total_servicos + total_insumos
    servicos_para_cobranca = list(servicos_itens)
    if plantao:
        acrescimo, item_plantao = financeiro_services.aplicar_plantao(total_servicos)
        total += acrescimo
        if item_plantao:
            servicos_para_cobranca.append(item_plantao)

    atendimento = Atendimento.objects.create(
        numero=_proximo_numero(), tipo=tipo,
        retorno_de=retorno_de if tipo == Atendimento.Tipo.RETORNO else None,
        vacina=vacina if vacinacao else None,
        vacina_nome=vacina.nome if vacinacao and vacina else "",
        dose=dose if vacinacao else "",
        data_proxima_dose=data_proxima_dose if vacinacao else None,
        data_retorno=None if vacinacao else data_retorno,
        lembrete_dias_antes=lembrete_dias_antes if (data_proxima_dose if vacinacao else data_retorno) else None,
        paciente=paciente,
        pac_nome=paciente.nome, pac_especie=paciente.get_especie_display(),
        tutor_nome=paciente.tutor.nome if paciente.tutor else "",
        tutor_tel=paciente.tutor.tel if paciente.tutor else "",
        data=data, hora=hora, servicos=servicos_itens, insumos=insumos_itens,
        plantao=plantao, obs=obs, total=total,
    )

    for insumo, qtd in debitos:
        debitar_para_consumo(
            insumo=insumo, quantidade=qtd, subtipo="consumo_atendimento",
            origem_tipo="atendimento", origem_id=atendimento.id, usuario=usuario,
        )

    financeiro_services.criar_cobranca_automatica(
        paciente=paciente, servicos_itens=servicos_para_cobranca, insumos_itens=insumos_itens,
        total=total, obs=f"Atendimento #{atendimento.numero} ({atendimento.get_tipo_display()})",
        atendimento=atendimento,
    )
    return atendimento


@transaction.atomic
def excluir_atendimento(atendimento: Atendimento, *, usuario) -> bool:
    """Exclusão = correção de cadastro: devolve ao estoque o que foi debitado
    e remove a cobrança se ainda estiver pendente. Cobrança já paga é
    mantida (dinheiro recebido não some por exclusão) — retorna True nesse
    caso, pra avisar o usuário."""
    estornar_consumo(origem_tipo="atendimento", origem_id=atendimento.id, usuario=usuario)
    atendimento.cobrancas.filter(status="pendente").delete()
    tinha_paga = atendimento.cobrancas.filter(status="pago").exists()
    atendimento.delete()
    return tinha_paga


def carteira_vacinacao(paciente) -> dict:
    """Histórico de vacinas do paciente + situação da próxima dose de cada
    vacina (considera só a aplicação mais recente de cada uma)."""
    from datetime import date

    aplicacoes = list(
        paciente.atendimentos.filter(tipo=Atendimento.Tipo.VACINACAO).order_by("-data", "-hora")
    )
    hoje = date.today()
    proximas, vistas = [], set()
    for aplicacao in aplicacoes:
        chave = aplicacao.vacina_id or aplicacao.vacina_nome
        if chave in vistas:
            continue
        vistas.add(chave)
        if aplicacao.data_proxima_dose:
            proximas.append({
                "aplicacao": aplicacao,
                "atrasada": aplicacao.data_proxima_dose < hoje,
                "dias": (aplicacao.data_proxima_dose - hoje).days,
            })
    proximas.sort(key=lambda p: p["aplicacao"].data_proxima_dose)
    return {"aplicacoes": aplicacoes, "proximas": proximas}
