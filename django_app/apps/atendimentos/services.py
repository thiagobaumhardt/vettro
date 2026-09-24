from django.db import transaction

from apps.estoque.services import debitar_para_consumo
from apps.financeiro import services as financeiro_services

from .models import Atendimento


@transaction.atomic
def criar_atendimento(*, paciente, data, hora, servico_ids, usos_insumos, plantao: bool, obs: str, usuario) -> Atendimento:
    servicos_itens, total_servicos = financeiro_services.montar_servicos(servico_ids)
    insumos_itens, total_insumos, debitos = financeiro_services.montar_insumos(usos_insumos)

    total = total_servicos + total_insumos
    if plantao and total_servicos > 0:
        acrescimo, _ = financeiro_services.aplicar_plantao(total_servicos)
        total += acrescimo

    atendimento = Atendimento.objects.create(
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

    # Sem criar_cobranca_automatica aqui — assimetria proposital (ver docstring do model).
    return atendimento
