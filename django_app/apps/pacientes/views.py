import json

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.auditoria.services import ip_da_requisicao, registrar as registrar_auditoria
from apps.core.decorators import admin_required, requer_secao, secoes_permitidas
from apps.estoque.models import Insumo
from apps.estoque.services import EstoqueInsuficienteError, insumos_para_busca
from apps.financeiro.models import Cobranca, CirurgiaCategoria, Servico
from apps.financeiro.services import ItemNaoEncontradoError
from apps.financeiro.services import servicos_do_post as financeiro_servicos_do_post
from apps.tutores.models import Tutor

from . import services as pacientes_services
from .forms import AnamneseForm, CirurgiaForm, CondicaoClinicaForm, NotaForm, PacienteForm
from .models import AnamneseHist, CirurgiaHist, CondicaoClinica, Exame, Foto, Nota, Paciente
from .racas import RACAS_POR_ESPECIE

# "vacinas" (carteira de vacinação) NÃO é aba clínica de propósito — a
# atendente precisa dela pra agendar o retorno da próxima dose.
# "historico" também não é clínica: o conteúdo já vem filtrado por perfil
# (pacientes_services.linha_do_tempo).
ABAS_DISPONIVEIS = {"ficha", "historico", "notas", "anamnese", "cirurgias", "exames", "fotos", "cobranca", "vacinas", "receitas", "documentos"}
ABAS_ADMIN_ONLY = {"cobranca"}
ABAS_CLINICAS = {"anamnese", "cirurgias", "exames", "fotos", "receitas", "documentos"}  # exige seção "pacientes_clinico"


@requer_secao("pacientes")
def lista(request):
    termo = request.GET.get("q", "").strip()
    pacientes = Paciente.objects.select_related("tutor").all()
    if termo:
        pacientes = pacientes.filter(Q(nome__icontains=termo) | Q(tutor__nome__icontains=termo))

    contexto = {"pacientes": pacientes, "termo": termo}
    template = "pacientes/_lista_resultado.html" if request.headers.get("HX-Request") else "pacientes/lista.html"
    return render(request, template, contexto)


@requer_secao("pacientes")
def form_view(request, pk=None):
    paciente = get_object_or_404(Paciente, pk=pk) if pk else None

    if request.method == "POST":
        form = PacienteForm(request.POST, request.FILES, instance=paciente)
        if form.is_valid():
            era_novo = paciente is None
            novo = form.save()
            registrar_auditoria(
                usuario=request.user, acao="criar" if era_novo else "atualizar",
                entidade="paciente", entidade_id=novo.id, detalhe=novo.nome, ip=ip_da_requisicao(request),
            )
            messages.success(request, "Paciente salvo com sucesso.")
            return redirect("pacientes:lista")
    else:
        form = PacienteForm(instance=paciente)

    return render(request, "pacientes/form.html", {
        "form": form,
        "paciente": paciente,
        "racas_json": json.dumps(RACAS_POR_ESPECIE),
    })


@requer_secao("pacientes_clinico")
def condicoes(request):
    """Catálogo de condições clínicas da clínica (admin/vet)."""
    form = CondicaoClinicaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Condição cadastrada.")
        return redirect("pacientes:condicoes")
    return render(request, "pacientes/condicoes.html", {
        "form": form,
        "condicoes": CondicaoClinica.objects.annotate(total_pacientes=Count("pacientes")),
    })


@requer_secao("pacientes_clinico")
def condicao_excluir(request, condicao_id):
    if request.method == "POST":
        get_object_or_404(CondicaoClinica, pk=condicao_id).delete()
        messages.success(request, "Condição excluída.")
    return redirect("pacientes:condicoes")


@requer_secao("pacientes")
def excluir(request, pk):
    paciente = get_object_or_404(Paciente, pk=pk)
    if request.method == "POST":
        nome, paciente_id = paciente.nome, paciente.id
        paciente.delete()
        registrar_auditoria(
            usuario=request.user, acao="excluir", entidade="paciente",
            entidade_id=paciente_id, detalhe=nome, ip=ip_da_requisicao(request),
        )
        messages.success(request, "Paciente excluído.")
        return redirect("pacientes:lista")
    return redirect("pacientes:ficha", pk=pk)


@requer_secao("pacientes")
def ficha(request, pk):
    paciente = get_object_or_404(Paciente, pk=pk)
    aba = request.GET.get("aba", "ficha")
    papel = request.session.get("papel")
    if (
        aba not in ABAS_DISPONIVEIS
        or (aba in ABAS_ADMIN_ONLY and papel != "admin")
        or (aba in ABAS_CLINICAS and "pacientes_clinico" not in secoes_permitidas(request))
    ):
        aba = "ficha"

    # Cirurgias não tem mais aba na barra — abre pelo botão "Procedimento
    # cirúrgico" da aba Atendimento, que fica destacada.
    contexto = {"paciente": paciente, "aba_ativa": aba, "aba_destaque": "anamnese" if aba == "cirurgias" else aba}
    if aba == "ficha":
        contexto.update(_contexto_ficha(request, paciente))
    elif aba == "historico":
        contexto.update(_contexto_historico(request, paciente))
    elif aba == "notas":
        contexto.update(notas=paciente.notas.all(), form=NotaForm())
    elif aba == "anamnese":
        contexto.update(_contexto_anamnese(paciente))
    elif aba == "cirurgias":
        contexto.update(_contexto_cirurgias(paciente))
    elif aba == "exames":
        contexto.update(_contexto_anexos(paciente, "exames"))
    elif aba == "fotos":
        contexto.update(_contexto_anexos(paciente, "fotos"))
    elif aba == "cobranca":
        contexto.update(_contexto_cobranca(paciente))
    elif aba == "vacinas":
        contexto.update(_contexto_vacinas(paciente))
    elif aba == "receitas":
        contexto.update(receitas=paciente.receitas.all())
    elif aba == "documentos":
        contexto.update(_contexto_documentos(paciente))

    return render(request, "pacientes/ficha.html", contexto)


@requer_secao("pacientes")
def ficha_aba(request, pk, aba):
    """Troca de aba via HTMX — retorna só o fragmento, hx-push-url mantém o
    deep-link (?aba=) e o botão voltar do navegador funcionando (§6 do plano).
    Aba Cobrança é admin-only e as abas clínicas exigem o perfil
    "pacientes_clinico" (§9-bis) — não aparecem no menu pra quem não tem
    acesso, e aqui são bloqueadas mesmo que a URL seja acessada direto."""
    paciente = get_object_or_404(Paciente, pk=pk)
    papel = request.session.get("papel")
    if aba not in ABAS_DISPONIVEIS:
        raise Http404
    if aba in ABAS_ADMIN_ONLY and papel != "admin":
        raise PermissionDenied("Aba restrita a administradores da clínica.")
    if aba in ABAS_CLINICAS and "pacientes_clinico" not in secoes_permitidas(request):
        raise PermissionDenied("Seu perfil não tem acesso a dados clínicos.")

    if aba == "ficha":
        return render(request, "pacientes/ficha/_ficha_info.html", _contexto_ficha(request, paciente))

    if aba == "historico":
        return render(request, "pacientes/ficha/_ficha_historico.html", _contexto_historico(request, paciente))

    if aba == "notas":
        notas = paciente.notas.all()
        return render(request, "pacientes/ficha/_ficha_notas.html", {
            "paciente": paciente, "notas": notas, "form": NotaForm(),
        })

    if aba == "cobranca":
        return render(request, "pacientes/ficha/_ficha_cobranca.html", _contexto_cobranca(paciente))

    if aba == "vacinas":
        return render(request, "pacientes/ficha/_ficha_vacinas.html", _contexto_vacinas(paciente))

    if aba == "receitas":
        return render(request, "pacientes/ficha/_ficha_receitas.html", {
            "paciente": paciente, "receitas": paciente.receitas.all(),
        })

    if aba == "documentos":
        return render(request, "pacientes/ficha/_ficha_documentos.html", _contexto_documentos(paciente))

    if aba == "anamnese":
        return render(request, "pacientes/ficha/_ficha_anamnese.html", _contexto_anamnese(paciente))

    if aba == "cirurgias":
        return render(request, "pacientes/ficha/_ficha_cirurgias.html", _contexto_cirurgias(paciente))

    if aba == "exames":
        return render(request, "pacientes/ficha/_ficha_exames.html", _contexto_anexos(paciente, "exames"))

    if aba == "fotos":
        return render(request, "pacientes/ficha/_ficha_fotos.html", _contexto_anexos(paciente, "fotos"))


# Detalhe de UM registro da linha do tempo (clicado em "Últimos atendimentos"
# ou no Histórico): mostra TODAS as informações do registro, em seções — campo
# vazio aparece como "—", nada fica escondido.
# tipo -> (seção exigida, aba destacada na barra).
REGISTROS = {
    "atendimento": ("atendimentos", "historico"),
    "consulta": ("pacientes_clinico", "anamnese"),
    "cirurgia": ("pacientes_clinico", "anamnese"),  # Cirurgias não tem aba própria: entra por Atendimento
}
SECOES_CONSULTA = [
    ("Queixa e histórico", ["queixa", "historico", "medicamentos", "alergias", "obs_add"]),
    ("Manejo e ambiente", ["alimentacao", "vacina", "verme", "rua", "convive"]),
    ("Avaliação física", [
        "av_fc", "av_fr", "av_pa", "av_temp", "av_hidratacao", "av_mucosas",
        "av_linf_sub", "av_linf_sube", "av_linf_ing", "av_linf_pop", "av_demais",
    ]),
]
SECOES_CIRURGIA = [("Cirurgia", ["proc", "anestesista", "clinica", "desc_cir", "pos_op"])]


def _campos(obj, nomes):
    """[(rótulo, valor, largura_total)] de TODOS os campos — vazio vira "—"."""
    campos = []
    for nome in nomes:
        field = obj._meta.get_field(nome)
        valor = getattr(obj, f"get_{nome}_display")() if field.choices else getattr(obj, nome)
        rotulo = str(field.verbose_name)
        campos.append((rotulo[:1].upper() + rotulo[1:], valor if valor not in ("", None) else "—",
                       field.get_internal_type() == "TextField"))
    return campos


def _data(valor, formato="%d/%m/%Y"):
    from django.utils import timezone

    if not valor:
        return "—"
    if getattr(valor, "tzinfo", None) is not None:
        valor = timezone.localtime(valor)
    return valor.strftime(formato)


def _com_subtotal(itens):
    """Snapshots antigos de insumo não guardavam o subtotal — calcula valor × qtd."""
    from decimal import Decimal, InvalidOperation

    saida = []
    for item in itens:
        item = dict(item)
        if not item.get("subtotal"):
            try:
                item["subtotal"] = str((Decimal(str(item["valor"])) * Decimal(str(item.get("qtd") or 1))).quantize(Decimal("0.01")))
            except (KeyError, InvalidOperation):
                pass
        saida.append(item)
    return saida


def _cobranca_do_registro(tipo, r):
    """Cobrança gerada pelo registro. Atendimento tem FK; Consulta/Cirurgia são
    achadas pelo texto fixo que criar_anamnese/criar_cirurgia gravam em `obs`,
    criadas no mesmo instante do registro."""
    from datetime import timedelta

    from apps.financeiro.models import Cobranca

    if tipo == "atendimento":
        return r.cobrancas.first()
    obs = f"Consulta de {r.data:%d/%m/%Y}" if tipo == "consulta" else f"Cirurgia: {r.proc}"
    return Cobranca.objects.filter(
        paciente=r.paciente, obs=obs,
        criado_em__gte=r.criado_em - timedelta(seconds=5), criado_em__lte=r.criado_em + timedelta(minutes=2),
    ).order_by("criado_em").first()


def _sim_nao(valor):
    return "Sim" if valor else "Não"


def _contexto_registro(request, paciente, tipo, registro_id):
    if tipo not in REGISTROS:
        raise Http404
    secao, aba = REGISTROS[tipo]
    if secao not in secoes_permitidas(request):
        raise PermissionDenied("Seu perfil não tem acesso a este registro.")

    if tipo == "atendimento":
        from apps.atendimentos.models import Atendimento
        from apps.pacientes.models import ESPECIE_CHOICES

        r = get_object_or_404(Atendimento.objects.select_related("retorno_de"), pk=registro_id, paciente=paciente)
        titulo, servicos = f"Atendimento #{r.numero} · {r.get_tipo_display()}", r.servicos
        secoes = [
            ("Dados do atendimento", [
                ("Número", f"#{r.numero}", False), ("Tipo", r.get_tipo_display(), False),
                ("Data", _data(r.data), False), ("Hora", _data(r.hora, "%H:%M"), False),
                ("Plantão", _sim_nao(r.plantao), False), ("Registrado em", _data(r.criado_em, "%d/%m/%Y %H:%M"), False),
            ]),
            ("Paciente e tutor (no dia do atendimento)", [
                ("Paciente", r.pac_nome or "—", False),
                ("Espécie", dict(ESPECIE_CHOICES).get(r.pac_especie, r.pac_especie) or "—", False),
                ("Tutor", r.tutor_nome or "—", False), ("Telefone do tutor", r.tutor_tel or "—", False),
            ]),
        ]
        if r.tipo == "vacinacao":
            secoes.append(("Vacinação", [
                ("Vacina", r.vacina_nome or "—", False), ("Dose", r.get_dose_display() or "—", False),
                ("Próxima dose", _data(r.data_proxima_dose), False),
            ]))
        retorno_de = (
            f"#{r.retorno_de.numero} ({r.retorno_de.get_tipo_display()}, {r.retorno_de.data:%d/%m/%Y})"
            if r.retorno_de else "—"
        )
        lembrete = f"{r.lembrete_dias_antes} dia(s) antes" if r.lembrete_dias_antes is not None else "Sem lembrete"
        enviado = _data(r.lembrete_enviado_em, "%d/%m/%Y %H:%M") if r.lembrete_enviado_em else "Não enviado"
        secoes.append(("Retorno e lembrete", [
            ("Retorno do atendimento", retorno_de, False), ("Retorno previsto", _data(r.data_retorno), False),
            ("Lembrete de WhatsApp", lembrete, False), ("Data do lembrete", _data(r.data_lembrete), False),
            ("Lembrete enviado em", enviado, False),
        ]))
        secoes.append(("Observações", [("Observações", r.obs or "—", True)]))
    else:
        modelo = AnamneseHist if tipo == "consulta" else CirurgiaHist
        r = get_object_or_404(modelo, pk=registro_id, paciente=paciente)
        dados = [
            ("Data", _data(r.data), False), ("Hora", _data(r.hora, "%H:%M"), False),
            ("Plantão", _sim_nao(r.plantao), False),
        ]
        if tipo == "cirurgia":
            dados.append(("Deslocamento (outra cidade)", _sim_nao(r.outra_cidade), False))
        dados.append(("Registrado em", _data(r.criado_em, "%d/%m/%Y %H:%M"), False))
        definicao = SECOES_CONSULTA if tipo == "consulta" else SECOES_CIRURGIA
        secoes = [("Dados do registro", dados)] + [(t, _campos(r, nomes)) for t, nomes in definicao]
        titulo = "Consulta" if tipo == "consulta" else f"Cirurgia · {r.proc}"
        servicos = r.servicos if tipo == "consulta" else r.procedimentos

    cobranca = _cobranca_do_registro(tipo, r) if request.session.get("papel") == "admin" else None
    return {
        "paciente": paciente, "registro": r, "registro_tipo": tipo, "registro_titulo": titulo,
        "registro_secoes": secoes, "registro_servicos": _com_subtotal(servicos),
        "registro_insumos": _com_subtotal(r.insumos), "registro_cobranca": cobranca, "aba_destaque": aba,
        "registro_exames": r.exames.all() if tipo == "atendimento" else [],
        "registro_fotos": r.fotos.all() if tipo == "atendimento" else [],
    }


@requer_secao("pacientes")
def registro(request, pk, tipo, registro_id):
    paciente = get_object_or_404(Paciente, pk=pk)
    contexto = _contexto_registro(request, paciente, tipo, registro_id)
    if request.headers.get("HX-Request"):
        return render(request, "pacientes/ficha/_registro.html", contexto)
    return render(request, "pacientes/ficha.html", {**contexto, "aba_ativa": "registro"})


RECENTES_NA_FICHA = 5


def _contexto_ficha(request, paciente):
    eventos = pacientes_services.linha_do_tempo(paciente, secoes_permitidas(request))
    return {
        "paciente": paciente,
        "linha_do_tempo": eventos[:RECENTES_NA_FICHA],
        "total_historico": len(eventos),
    }


def _contexto_historico(request, paciente):
    eventos = pacientes_services.linha_do_tempo(paciente, secoes_permitidas(request))
    presentes = {e["categoria"] for e in eventos}
    return {
        "paciente": paciente,
        "linha_do_tempo": eventos,
        # Só os filtros que têm algum registro deste paciente.
        "categorias": [(c, rotulo) for c, rotulo in pacientes_services.CATEGORIAS_HISTORICO.items() if c in presentes],
    }


def _contexto_documentos(paciente):
    from apps.documentos.models import ModeloDocumento

    return {
        "paciente": paciente, "documentos": paciente.documentos.all(),
        "modelos": ModeloDocumento.objects.filter(ativo=True),
    }


def _contexto_vacinas(paciente):
    from apps.atendimentos.services import carteira_vacinacao

    return {"paciente": paciente, **carteira_vacinacao(paciente)}


def _contexto_anamnese(paciente, erro=None):
    servicos = list(Servico.objects.all())
    insumos = list(Insumo.objects.all())
    return {
        "paciente": paciente, "form": AnamneseForm(),
        "servicos": servicos, "insumos": insumos,
        "servicos_json": json.dumps([{"id": str(s.id), "valor": str(s.valor)} for s in servicos]),
        "insumos_json": json.dumps(insumos_para_busca(insumos)),
        "erro": erro,
    }


def _contexto_cirurgias(paciente, erro=None):
    from apps.financeiro.services import valor_por_peso

    categorias = list(CirurgiaCategoria.objects.all())
    insumos = list(Insumo.objects.all())
    return {
        "paciente": paciente, "form": CirurgiaForm(),
        "categorias": categorias, "insumos": insumos,
        # valor já resolvido pela faixa de peso DESTE paciente — o preview
        # do total no navegador precisa bater com o que o servidor vai
        # calcular de verdade no submit (apps.financeiro.services.valor_por_peso).
        "categorias_json": json.dumps([
            {"id": str(c.id), "nome": c.nome, "valor": str(valor_por_peso(c, paciente.peso))} for c in categorias
        ]),
        "insumos_json": json.dumps(insumos_para_busca(insumos)),
        "historico": paciente.cirurgias.all(), "erro": erro,
        "faixa_peso_label": _faixa_peso_label(paciente.peso),
    }


def _contexto_cobranca(paciente, erro=None):
    servicos = list(Servico.objects.all())
    insumos = list(Insumo.objects.all())
    return {
        "paciente": paciente, "servicos": servicos, "insumos": insumos,
        "servicos_json": json.dumps([{"id": str(s.id), "valor": str(s.valor)} for s in servicos]),
        "insumos_json": json.dumps(insumos_para_busca(insumos)),
        "historico": paciente.cobrancas.all(), "erro": erro,
    }


@admin_required
def cobranca_criar(request, pk):
    """Cobrança manual — mesmo padrão de montar_servicos/montar_insumos de
    Anamnese/Cirurgia, mas sem campos clínicos (porte de
    backend/app/routers/cobrancas.py, admin only)."""
    from apps.financeiro import services as financeiro_services
    from apps.estoque.services import debitar_para_consumo

    paciente = get_object_or_404(Paciente, pk=pk)
    usos_servicos = financeiro_services.servicos_do_post(request.POST)
    usos_insumos = pacientes_services.usos_insumos_do_post(request.POST)
    obs = request.POST.get("obs", "")

    if not usos_servicos and not usos_insumos:
        return render(request, "pacientes/ficha/_ficha_cobranca.html", {
            **_contexto_cobranca(paciente), "erro": "Selecione ao menos um serviço ou insumo.",
        })

    try:
        # Atômico: se um débito de estoque falhar, a cobrança também não fica.
        with transaction.atomic():
            servicos_itens, total_servicos = financeiro_services.montar_servicos(usos_servicos)
            insumos_itens, total_insumos, debitos = financeiro_services.montar_insumos(usos_insumos)
            cobranca = Cobranca.objects.create(
                paciente=paciente, servicos=servicos_itens, insumos=insumos_itens,
                total=total_servicos + total_insumos, status="pendente",
                tutor_nome=paciente.tutor.nome if paciente.tutor else "", obs=obs,
            )
            for insumo, qtd in debitos:
                debitar_para_consumo(
                    insumo=insumo, quantidade=qtd, subtipo="venda_produto",
                    origem_tipo="cobranca", origem_id=cobranca.id, usuario=request.user,
                )
        messages.success(request, "Cobrança registrada. Estoque atualizado.")
    except (EstoqueInsuficienteError, ItemNaoEncontradoError) as exc:
        return render(request, "pacientes/ficha/_ficha_cobranca.html", {**_contexto_cobranca(paciente), "erro": str(exc)})

    return render(request, "pacientes/ficha/_ficha_cobranca.html", _contexto_cobranca(paciente))


@admin_required
def cobranca_excluir(request, pk, cobranca_id):
    paciente = get_object_or_404(Paciente, pk=pk)
    if request.method == "POST":
        _excluir_com_estorno(Cobranca.objects.filter(pk=cobranca_id, paciente=paciente), "cobranca", request.user)
    return render(request, "pacientes/ficha/_ficha_cobranca.html", _contexto_cobranca(paciente))


def _excluir_com_estorno(queryset, origem_tipo, usuario):
    """Exclui o registro e devolve ao estoque os insumos que ele debitou."""
    from apps.estoque.services import estornar_consumo

    with transaction.atomic():
        for registro in queryset:
            estornar_consumo(origem_tipo=origem_tipo, origem_id=registro.pk, usuario=usuario)
            registro.delete()


def _faixa_peso_label(peso):
    if not peso:
        return None
    if peso < 10:
        return f"Faixa: até 10kg ({peso} kg)"
    if peso <= 25:
        return f"Faixa: 10–25kg ({peso} kg)"
    return f"Faixa: acima de 25kg ({peso} kg)"


@requer_secao("pacientes_clinico")
def anamnese_criar(request, pk):
    paciente = get_object_or_404(Paciente, pk=pk)
    form = AnamneseForm(request.POST)
    if form.is_valid():
        try:
            pacientes_services.criar_anamnese(
                paciente=paciente, dados_clinicos=form.cleaned_data,
                servico_ids=financeiro_servicos_do_post(request.POST),
                usos_insumos=pacientes_services.usos_insumos_do_post(request.POST),
                plantao=request.POST.get("plantao") == "on",
                usuario=request.user,
            )
            messages.success(request, "Consulta registrada. Cobrança gerada automaticamente, se aplicável.")
            return render(request, "pacientes/ficha/_ficha_anamnese.html", _contexto_anamnese(paciente))
        except (EstoqueInsuficienteError, ItemNaoEncontradoError) as exc:
            return render(request, "pacientes/ficha/_ficha_anamnese.html", _contexto_anamnese(paciente, erro=str(exc)))
    return render(request, "pacientes/ficha/_ficha_anamnese.html", {
        **_contexto_anamnese(paciente), "form": form, "erro": "Verifique os campos do formulário.",
    })


@requer_secao("pacientes_clinico")
def anamnese_excluir(request, pk, anamnese_id):
    paciente = get_object_or_404(Paciente, pk=pk)
    if request.method == "POST":
        _excluir_com_estorno(AnamneseHist.objects.filter(pk=anamnese_id, paciente=paciente), "anamnese", request.user)
    return render(request, "pacientes/ficha/_ficha_anamnese.html", _contexto_anamnese(paciente))


@requer_secao("pacientes_clinico")
def cirurgia_criar(request, pk):
    paciente = get_object_or_404(Paciente, pk=pk)
    form = CirurgiaForm(request.POST)
    if form.is_valid():
        try:
            pacientes_services.criar_cirurgia(
                paciente=paciente, dados=form.cleaned_data,
                categoria_ids=request.POST.getlist("categoria_ids"),
                usos_insumos=pacientes_services.usos_insumos_do_post(request.POST),
                plantao=request.POST.get("plantao") == "on",
                outra_cidade=request.POST.get("outra_cidade") == "on",
                usuario=request.user,
            )
            messages.success(request, "Cirurgia registrada. Cobrança gerada automaticamente, se aplicável.")
            return render(request, "pacientes/ficha/_ficha_cirurgias.html", _contexto_cirurgias(paciente))
        except (EstoqueInsuficienteError, ItemNaoEncontradoError) as exc:
            return render(request, "pacientes/ficha/_ficha_cirurgias.html", _contexto_cirurgias(paciente, erro=str(exc)))
    return render(request, "pacientes/ficha/_ficha_cirurgias.html", {
        **_contexto_cirurgias(paciente), "form": form, "erro": "Verifique os campos do formulário.",
    })


@requer_secao("pacientes_clinico")
def cirurgia_excluir(request, pk, cirurgia_id):
    paciente = get_object_or_404(Paciente, pk=pk)
    if request.method == "POST":
        _excluir_com_estorno(CirurgiaHist.objects.filter(pk=cirurgia_id, paciente=paciente), "cirurgia", request.user)
    return render(request, "pacientes/ficha/_ficha_cirurgias.html", _contexto_cirurgias(paciente))


def _contexto_anexos(paciente, tipo, erro=None):
    """Abas Exames/Fotos: histórico + atendimentos do paciente pro seletor
    "Vincular ao atendimento" do formulário de anexar."""
    itens = (paciente.exames if tipo == "exames" else paciente.fotos).select_related("atendimento")
    return {
        "paciente": paciente, tipo: itens, "erro": erro,
        "atendimentos_paciente": paciente.atendimentos.order_by("-data", "-hora", "-numero"),
    }


def _atendimento_do_post(request, paciente):
    """Atendimento escolhido no formulário — só aceita um do PRÓPRIO paciente."""
    atendimento_id = request.POST.get("atendimento") or None
    if not atendimento_id:
        return None, None
    atendimento = paciente.atendimentos.filter(pk=atendimento_id).first()
    return atendimento, (None if atendimento else "Atendimento escolhido não pertence a este paciente.")


def _nome_do_anexo(request, arquivo, indice, total):
    """Nome digitado (com numeração se vierem vários arquivos) ou o nome do arquivo."""
    nome = request.POST.get("nome", "").strip()
    if not nome:
        return arquivo.name
    return f"{nome} ({indice})" if total > 1 else nome


@requer_secao("pacientes_clinico")
def exame_upload(request, pk):
    paciente = get_object_or_404(Paciente, pk=pk)
    erro = None
    if request.method == "POST":
        atendimento, erro = _atendimento_do_post(request, paciente)
        arquivos = request.FILES.getlist("arquivos")
        if not erro and not arquivos:
            erro = "Escolha ao menos um arquivo PDF."
        if not erro:
            for indice, arquivo in enumerate(arquivos, 1):
                if not arquivo.name.lower().endswith(".pdf"):
                    messages.error(request, f"{arquivo.name} não é um PDF e foi ignorado.")
                    continue
                Exame.objects.create(
                    paciente=paciente, atendimento=atendimento, arquivo=arquivo,
                    nome=_nome_do_anexo(request, arquivo, indice, len(arquivos)),
                )
    return render(request, "pacientes/ficha/_ficha_exames.html", _contexto_anexos(paciente, "exames", erro))


@requer_secao("pacientes_clinico")
def exame_excluir(request, pk, exame_id):
    paciente = get_object_or_404(Paciente, pk=pk)
    if request.method == "POST":
        Exame.objects.filter(pk=exame_id, paciente=paciente).delete()
    return render(request, "pacientes/ficha/_ficha_exames.html", _contexto_anexos(paciente, "exames"))


@requer_secao("pacientes_clinico")
def foto_upload(request, pk):
    paciente = get_object_or_404(Paciente, pk=pk)
    erro = None
    if request.method == "POST":
        atendimento, erro = _atendimento_do_post(request, paciente)
        arquivos = request.FILES.getlist("arquivos")
        if not erro and not arquivos:
            erro = "Escolha ao menos uma foto."
        if not erro:
            for indice, arquivo in enumerate(arquivos, 1):
                if not arquivo.content_type.startswith("image/"):
                    messages.error(request, f"{arquivo.name} não é uma imagem e foi ignorado.")
                    continue
                Foto.objects.create(
                    paciente=paciente, atendimento=atendimento, imagem=arquivo,
                    nome=_nome_do_anexo(request, arquivo, indice, len(arquivos)),
                )
    return render(request, "pacientes/ficha/_ficha_fotos.html", _contexto_anexos(paciente, "fotos", erro))


@requer_secao("pacientes_clinico")
def foto_excluir(request, pk, foto_id):
    paciente = get_object_or_404(Paciente, pk=pk)
    if request.method == "POST":
        Foto.objects.filter(pk=foto_id, paciente=paciente).delete()
    return render(request, "pacientes/ficha/_ficha_fotos.html", _contexto_anexos(paciente, "fotos"))


@requer_secao("pacientes")
def nota_criar(request, pk):
    paciente = get_object_or_404(Paciente, pk=pk)
    form = NotaForm(request.POST)
    if form.is_valid():
        nota = form.save(commit=False)
        nota.paciente = paciente
        nota.save()
    notas = paciente.notas.all()
    return render(request, "pacientes/ficha/_ficha_notas.html", {
        "paciente": paciente, "notas": notas, "form": NotaForm(),
    })


@requer_secao("pacientes")
def nota_editar(request, pk, nota_id):
    paciente = get_object_or_404(Paciente, pk=pk)
    nota = get_object_or_404(Nota, pk=nota_id, paciente=paciente)

    if request.method == "POST":
        form = NotaForm(request.POST, instance=nota)
        if form.is_valid():
            nota = form.save(commit=False)
            nota.editado_em = timezone.now()
            nota.save()
        notas = paciente.notas.all()
        return render(request, "pacientes/ficha/_ficha_notas.html", {
            "paciente": paciente, "notas": notas, "form": NotaForm(),
        })

    form = NotaForm(instance=nota)
    notas = paciente.notas.all()
    return render(request, "pacientes/ficha/_ficha_notas.html", {
        "paciente": paciente, "notas": notas, "form": form, "editando_id": str(nota.pk),
    })


@requer_secao("pacientes")
def nota_excluir(request, pk, nota_id):
    paciente = get_object_or_404(Paciente, pk=pk)
    if request.method == "POST":
        Nota.objects.filter(pk=nota_id, paciente=paciente).delete()
    notas = paciente.notas.all()
    return render(request, "pacientes/ficha/_ficha_notas.html", {
        "paciente": paciente, "notas": notas, "form": NotaForm(),
    })
