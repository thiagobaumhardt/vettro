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
        total=total, obs=f"Consulta de {anamnese.data:%d/%m/%Y}",
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


ICONES_ATENDIMENTO = {
    "vacinacao": "💉", "retorno": "↩", "aplicacao_medicacao": "💊", "curativo": "🩹", "emergencia": "🚨",
}
CATEGORIAS_HISTORICO = {
    "atendimento": "Atendimentos", "vacinacao": "Vacinas", "ficha_clinica": "Consultas",
    "cirurgia": "Cirurgias", "receita": "Receitas", "documento": "Documentos", "nota": "Anotações",
}


def linha_do_tempo(paciente, secoes: set) -> list[dict]:
    """Histórico do paciente, do mais recente pro mais antigo: Atendimentos
    (inclui vacinação/retorno), fichas clínicas (Anamnese), Cirurgias,
    Receitas e Documentos emitidos. Só entra o que o perfil pode ver —
    Atendimentos exigem "atendimentos", o resto exige "pacientes_clinico"."""
    from django.urls import reverse
    from django.utils import timezone

    eventos = []
    if "atendimentos" in secoes:
        for a in paciente.atendimentos.select_related("retorno_de"):
            if a.tipo == "vacinacao":
                detalhe = f"{a.vacina_nome} · {a.get_dose_display()}"
                if a.data_proxima_dose:
                    detalhe += f" · próxima em {a.data_proxima_dose:%d/%m/%Y}"
            elif a.tipo == "retorno":
                detalhe = f"Retorno de #{a.retorno_de.numero}" if a.retorno_de else "Retorno"
            else:
                detalhe = ", ".join(s["nome"] for s in a.servicos)
            if a.data_retorno:
                detalhe = " · ".join(filter(None, [detalhe, f"retorno previsto para {a.data_retorno:%d/%m/%Y}"]))
            eventos.append({
                "data": a.data, "hora": a.hora, "icone": ICONES_ATENDIMENTO.get(a.tipo, "🩺"),
                "titulo": f"#{a.numero} · {a.get_tipo_display()}", "detalhe": detalhe,
                "obs": a.obs, "total": a.total, "plantao": a.plantao,
                "categoria": "vacinacao" if a.tipo == "vacinacao" else "atendimento",
                "url": reverse("pacientes:registro", args=[paciente.pk, "atendimento", a.pk]),
                "na_ficha": True, "aba": "historico",
            })
    if "pacientes_clinico" in secoes:
        for an in paciente.anamneses.all():
            eventos.append({
                "data": an.data, "hora": an.hora, "icone": "📋", "titulo": "Consulta",
                "detalhe": an.queixa, "obs": "", "total": an.total, "plantao": an.plantao,
                "categoria": "ficha_clinica", "na_ficha": True, "aba": "anamnese",
                "url": reverse("pacientes:registro", args=[paciente.pk, "consulta", an.pk]),
            })
        for c in paciente.cirurgias.all():
            eventos.append({
                "data": c.data, "hora": c.hora, "icone": "🔪", "titulo": "Cirurgia",
                "detalhe": c.proc, "obs": "", "total": c.total, "plantao": c.plantao,
                "categoria": "cirurgia", "na_ficha": True, "aba": "anamnese",
                "url": reverse("pacientes:registro", args=[paciente.pk, "cirurgia", c.pk]),
            })
        for r in paciente.receitas.all():
            quando = timezone.localtime(r.criado_em)
            conteudo = r.texto if r.tipo == "livre" else ", ".join(i["medicamento"] for i in r.itens)
            eventos.append({
                "data": quando.date(), "hora": quando.time(), "icone": "💊", "titulo": r.get_tipo_display(),
                "detalhe": conteudo, "obs": f"Emitida por {r.vet_nome}" if r.vet_nome else "", "total": None,
                "plantao": False, "categoria": "receita",
                "url": reverse("receitas:detalhe", args=[paciente.pk, r.pk]),
            })
        for d in paciente.documentos.all():
            quando = timezone.localtime(d.criado_em)
            eventos.append({
                "data": quando.date(), "hora": quando.time(), "icone": "📄", "titulo": d.titulo,
                "detalhe": "", "obs": f"Emitido por {d.vet_nome}" if d.vet_nome else "", "total": None,
                "plantao": False, "categoria": "documento", "url": reverse("documentos:detalhe", args=[d.pk]),
            })
    if "pacientes" in secoes:
        # Anotações: qualquer perfil com acesso a Pacientes vê (igual à aba Anotações).
        ficha = reverse("pacientes:ficha", args=[paciente.pk])
        for n in paciente.notas.all():
            quando = timezone.localtime(n.criado_em)
            eventos.append({
                "data": quando.date(), "hora": quando.time(),
                "titulo": f"Anotação · {n.titulo}" if n.titulo else "Anotação",
                "detalhe": n.conteudo, "obs": f"Editada em {timezone.localtime(n.editado_em):%d/%m/%Y %H:%M}" if n.editado_em else "",
                "total": None, "plantao": False, "categoria": "nota",
                "na_ficha": True, "aba": "notas", "url": f"{ficha}?aba=notas",
                "hx_url": reverse("pacientes:ficha_aba", args=[paciente.pk, "notas"]),
            })
    eventos.sort(key=lambda e: (e["data"], e["hora"]), reverse=True)
    return eventos


def usos_insumos_do_post(post) -> list[dict]:
    """Lê os checkboxes `insumo_ids` + inputs `qtd_<id>` do POST — mesmo
    padrão usado em Anamnese/Cirurgia/Atendimentos. A quantidade está na
    unidade de uso e pode ser fração ("2,5" ml); financeiro.montar_insumos
    valida (e recusa zero/negativo/texto com mensagem)."""
    return [
        {"insumo_id": insumo_id, "qtd": post.get(f"qtd_{insumo_id}") or "1"}
        for insumo_id in post.getlist("insumo_ids")
    ]
