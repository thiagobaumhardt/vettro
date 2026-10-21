import calendar
import json
from datetime import date, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.decorators import admin_required, requer_secao
from apps.financeiro.models import Servico
from apps.pacientes.models import Paciente

from . import services
from .forms import AgendamentoForm, BloqueioForm, ConsultorioForm
from .models import Agendamento, BloqueioAgenda, Consultorio

MESES_PT = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]
DIAS_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
VISOES = ("dia", "semana", "mes", "fila")


def _data_param(valor, padrao):
    try:
        return date.fromisoformat(valor) if valor else padrao
    except ValueError:
        return padrao


def _filtros(request) -> dict:
    g = request.GET
    return {
        "consultorio": g.get("consultorio", ""), "servico": g.get("servico", ""),
        "status": g.get("status", ""),
    }


def _url_agenda(visao: str, data_ref: date, filtros: dict) -> str:
    params = {"visao": visao, "data": data_ref.isoformat(), **{k: v for k, v in filtros.items() if v}}
    return f"{reverse('agenda:calendario')}?{urlencode(params)}"


def _base_queryset(filtros: dict):
    qs = Agendamento.objects.select_related("consultorio", "paciente")
    if filtros["consultorio"] == "sem":
        qs = qs.filter(consultorio__isnull=True)
    elif filtros["consultorio"]:
        qs = qs.filter(consultorio_id=filtros["consultorio"])
    if filtros["servico"]:
        qs = qs.filter(servicos__contains=[{"id": filtros["servico"]}])
    if filtros["status"]:
        qs = qs.filter(status=filtros["status"])
    else:
        qs = qs.exclude(status="cancelado")  # cancelados só aparecem filtrando por eles
    return qs


def _voltar(request, padrao: str) -> str:
    voltar = request.POST.get("voltar") or request.GET.get("voltar") or ""
    return voltar if voltar.startswith("/agenda/") else padrao


# --- Visões -----------------------------------------------------------------------------

@requer_secao("agenda")
def calendario(request):
    hoje = timezone.localdate()
    visao = request.GET.get("visao", "dia")
    visao = visao if visao in VISOES else "dia"
    data_ref = _data_param(request.GET.get("data") or request.GET.get("dia"), hoje)
    filtros = _filtros(request)
    cfg = services.config_agenda()
    todos_consultorios = list(Consultorio.objects.filter(ativo=True))
    # Quais consultórios/locais ver (botão "Locais"): escolha guardada na sessão de cada usuário.
    if "ver_todos" in request.GET:
        request.session["agenda_ver"] = []
    elif "ver" in request.GET:
        request.session["agenda_ver"] = request.GET.getlist("ver")
    validos = {str(c.pk) for c in todos_consultorios}
    ver = [v for v in request.session.get("agenda_ver", []) if v in validos]
    consultorios = [c for c in todos_consultorios if str(c.pk) in ver] if ver else todos_consultorios
    qs = _base_queryset(filtros)
    if ver:
        qs = qs.filter(consultorio_id__in=ver)
    cons_filtro = filtros["consultorio"] if filtros["consultorio"] not in ("", "sem") else None

    if visao in ("dia", "fila"):
        anterior, proximo = data_ref - timedelta(days=1), data_ref + timedelta(days=1)
        titulo = f"{DIAS_PT[data_ref.weekday()]}, {data_ref.day} de {MESES_PT[data_ref.month].lower()} de {data_ref.year}"
    elif visao == "semana":
        inicio_semana = services.inicio_da_semana(data_ref)
        anterior, proximo = data_ref - timedelta(days=7), data_ref + timedelta(days=7)
        fim_semana = inicio_semana + timedelta(days=6)
        titulo = f"{inicio_semana:%d/%m} a {fim_semana:%d/%m/%Y}"
    else:
        ano, mes = data_ref.year, data_ref.month
        anterior = date(ano - 1, 12, 1) if mes == 1 else date(ano, mes - 1, 1)
        proximo = date(ano + 1, 1, 1) if mes == 12 else date(ano, mes + 1, 1)
        titulo = f"{MESES_PT[mes]} de {ano}"

    contexto = {
        "visao": visao, "data_ref": data_ref, "hoje": hoje, "titulo": titulo, "filtros": filtros,
        "url_anterior": _url_agenda(visao, anterior, filtros), "url_proximo": _url_agenda(visao, proximo, filtros),
        "url_hoje": _url_agenda(visao, hoje, filtros),
        "n_filtros": sum(1 for v in filtros.values() if v),
        "urls_visao": {v: _url_agenda(v, data_ref, filtros) for v in VISOES},
        "voltar": request.get_full_path(),
        "consultorios": todos_consultorios, "ver": ver, "n_locais": len(consultorios),
        "status_choices": Agendamento.STATUS_CHOICES,
        "servicos": Servico.objects.all(), "cfg": cfg, "altura_linha": str(services.ALTURA_LINHA),
    }

    # Cancelados não ocupam a grade (horário livre), mas ficam listados num cantinho pra saber que existiram.
    cancelados_qs = _base_queryset({**filtros, "status": "cancelado"}) if filtros["status"] != "cancelado" else None
    if cancelados_qs is not None and ver:
        cancelados_qs = cancelados_qs.filter(consultorio_id__in=ver)

    if visao == "dia":
        do_dia = list(qs.filter(data=data_ref).order_by("hora"))
        cancelados_dia = list(cancelados_qs.filter(data=data_ref).order_by("hora")) if cancelados_qs is not None else []
        contexto["cancelados"] = cancelados_dia
        colunas = []
        # Uma coluna por consultório (+ "Sem consultório" se houver agendamento sem local).
        alvo = [c for c in consultorios if str(c.pk) == cons_filtro] if cons_filtro else consultorios
        if filtros["consultorio"] != "sem":
            for c in alvo:
                ags = [a for a in do_dia if a.consultorio_id == c.pk]
                bloqueios = services.bloqueios_no_periodo(data_ref, data_ref, consultorio_id=c.pk)
                colunas.append({"titulo": c.nome, "consultorio_id": str(c.pk),
                                "cancelados": services.posicionar_cancelados([x for x in cancelados_dia if x.consultorio_id == c.pk], cfg),
                                **services.montar_coluna(ags, bloqueios, data_ref, cfg)})
        sem_local = [a for a in do_dia if not a.consultorio_id]
        if sem_local or (not colunas and not ver):
            bloqueios = services.bloqueios_no_periodo(data_ref, data_ref)
            colunas.append({"titulo": "Sem consultório", "consultorio_id": "",
                            **services.montar_coluna(sem_local, bloqueios, data_ref, cfg)})
        contexto.update(colunas=colunas, linhas=services.linhas_da_grade(cfg), total_dia=len(do_dia),
                        sem_horario=[a for c in colunas for a in c["sem_horario"]],
                        agora_top=services.posicao_agora(data_ref, cfg),
                        altura_grade=str(len(services.linhas_da_grade(cfg)) * services.ALTURA_LINHA))

    elif visao == "semana":
        inicio_semana = services.inicio_da_semana(data_ref)
        dias = [inicio_semana + timedelta(days=i) for i in range(7)]
        da_semana = list(qs.filter(data__gte=dias[0], data__lte=dias[-1]).order_by("hora"))
        cancelados_sem = list(cancelados_qs.filter(data__gte=dias[0], data__lte=dias[-1]).order_by("data", "hora")) if cancelados_qs is not None else []
        contexto["cancelados"] = cancelados_sem
        bloqueios = services.bloqueios_no_periodo(dias[0], dias[-1], consultorio_id=cons_filtro)
        colunas = [{"titulo": f"{DIAS_PT[d.weekday()][:3]} {d:%d/%m}", "data": d, "hoje": d == hoje,
                    "cancelados": services.posicionar_cancelados([x for x in cancelados_sem if x.data == d], cfg),
                    **services.montar_coluna([a for a in da_semana if a.data == d], bloqueios, d, cfg)}
                   for d in dias]
        contexto.update(colunas=colunas, linhas=services.linhas_da_grade(cfg),
                        agora_top_semana=services.posicao_agora(hoje, cfg),
                        total_semana=len(da_semana),
                        sem_horario=[a for c in colunas for a in c["sem_horario"]],
                        altura_grade=str(len(services.linhas_da_grade(cfg)) * services.ALTURA_LINHA))

    elif visao == "mes":
        ano, mes = data_ref.year, data_ref.month
        semanas = calendar.Calendar(firstweekday=6).monthdatescalendar(ano, mes)
        primeiro, ultimo = semanas[0][0], semanas[-1][-1]
        do_mes = list(qs.filter(data__gte=primeiro, data__lte=ultimo).order_by("hora"))
        bloqueios = services.bloqueios_no_periodo(primeiro, ultimo, consultorio_id=cons_filtro)
        por_dia = {}
        for a in do_mes:
            por_dia.setdefault(a.data, []).append(a)
        contexto.update(semanas=[[{
            "data": d, "do_mes": d.month == mes, "hoje": d == hoje,
            "ags": por_dia.get(d, []),
            "fechado": next((b for b in bloqueios if b.cobre(d) and b.faixa is None), None),
            "url": _url_agenda("dia", d, filtros),
        } for d in semana] for semana in semanas])

    else:  # fila (ordem de chegada) do dia
        do_dia = list(qs.filter(data=data_ref))
        agora = timezone.now()
        aguardando = sorted([a for a in do_dia if a.status == "aguardando"], key=lambda a: a.chegada_em or agora)
        for a in aguardando:
            a.esperando_min = round((agora - a.chegada_em).total_seconds() / 60) if a.chegada_em else None
        em_atendimento = sorted([a for a in do_dia if a.status == "em_atendimento"],
                                key=lambda a: a.inicio_atendimento_em or agora)
        for a in em_atendimento:
            a.atendendo_min = round((agora - a.inicio_atendimento_em).total_seconds() / 60) if a.inicio_atendimento_em else None
        previstos = sorted([a for a in do_dia if a.status == "agendado"],
                           key=lambda a: (a.hora is None, a.hora))
        finalizados = sorted([a for a in do_dia if a.status in ("realizado", "cancelado")],
                             key=lambda a: a.fim_atendimento_em or agora, reverse=True)
        contexto.update(
            aguardando=aguardando, em_atendimento=em_atendimento, previstos=previstos, finalizados=finalizados,
            metricas_dia=services.metricas_tempos(desde=data_ref, ate=data_ref, consultorio_id=cons_filtro),
            metricas_30=services.metricas_tempos(desde=data_ref - timedelta(days=29), ate=data_ref, consultorio_id=cons_filtro),
        )

    return render(request, "agenda/agenda.html", contexto)


# --- Criar / editar ------------------------------------------------------------------------

def _contexto_form(request, form, agendamento=None):
    pacientes = list(Paciente.objects.select_related("tutor").all())
    from apps.financeiro.models import TipoExame

    servicos = list(Servico.objects.filter(na_agenda=True))
    selecionados = {s["id"] for s in agendamento.servicos} if agendamento else set(request.POST.getlist("servico_ids") or request.GET.getlist("servico"))
    exames_sel = {e["id"] for e in agendamento.exames} if agendamento else set(request.POST.getlist("exame_ids"))
    return {
        "form": form, "agendamento": agendamento, "servicos_selecionados": selecionados, "servicos": servicos,
        "exames": TipoExame.objects.filter(ativo=True), "exames_selecionados": exames_sel,
        "voltar": _voltar(request, reverse("agenda:calendario")),
        "chegou": request.GET.get("chegou") == "1" or request.POST.get("chegou") == "1",
        "servicos_json": json.dumps({str(s.id): s.duracao_min for s in servicos}),
        "inicial_json": json.dumps({
            "paciente": str(form["paciente"].value() or ""), "pac_nome": form["pac_nome"].value() or "",
            "tutor_nome": form["tutor_nome"].value() or "", "tutor_tel": form["tutor_tel"].value() or "",
            "duracao": (agendamento.duracao_min if agendamento else None) or services.config_agenda()["intervalo"],
            "duracao_padrao": services.config_agenda()["intervalo"],
        }),
        "pacientes_json": json.dumps([
            {"id": str(p.id), "nome": p.nome, "tutor_nome": p.tutor.nome if p.tutor else "",
             "tutor_tel": p.tutor.tel if p.tutor else ""}
            for p in pacientes
        ]),
    }


def _aplicar_form(request, form):
    """Campos que não são do ModelForm: paciente resolvido e serviços."""
    resolvido = services.resolver_paciente(
        paciente=form.cleaned_data["paciente"], pac_nome=form.cleaned_data["pac_nome"],
        tutor_nome=form.cleaned_data["tutor_nome"], tutor_tel=form.cleaned_data["tutor_tel"],
    )
    ag = form.save(commit=False)
    ag.paciente, ag.pac_nome = resolvido["paciente"], resolvido["pac_nome"]
    ag.tutor_nome, ag.tutor_tel = resolvido["tutor_nome"], resolvido["tutor_tel"]
    ag.servicos = [
        {"id": str(s.id), "nome": s.nome, "valor": str(s.valor), "tipo": s.tipo}
        for s in Servico.objects.filter(pk__in=request.POST.getlist("servico_ids"))
    ]
    from apps.financeiro.models import TipoExame

    ag.exames = [
        {"id": str(e.id), "nome": e.nome, "duracao_min": e.duracao_min}
        for e in TipoExame.objects.filter(pk__in=request.POST.getlist("exame_ids"))
    ]
    return ag


@requer_secao("agenda")
def novo(request):
    clinica_id = request.session.get("clinica_id")
    if request.method == "POST":
        form = AgendamentoForm(request.POST, clinica_id=clinica_id)
        if form.is_valid():
            ag = _aplicar_form(request, form)
            if request.POST.get("chegou") == "1":  # chegada sem agendamento (ordem de chegada)
                ag.status, ag.chegada_em = "aguardando", timezone.now()
            ag.save()
            messages.success(request, "Agendamento salvo.")
            padrao = _url_agenda("fila" if request.POST.get("chegou") == "1" else "dia", ag.data, _filtros(request))
            return redirect(_voltar(request, padrao))
    else:
        cfg = services.config_agenda()
        g = request.GET
        servico = Servico.objects.filter(pk=g.get("servico") or None).first()
        inicial = {
            "data": _data_param(g.get("data"), timezone.localdate()),
            "hora": g.get("hora") or (services.hora_atual_arredondada(cfg).strftime("%H:%M") if g.get("chegou") == "1" else None),
            "consultorio": g.get("consultorio") or None, "paciente": g.get("paciente") or None,
            "encaixe": g.get("encaixe") == "1" or g.get("chegou") == "1",
        }
        form = AgendamentoForm(initial=inicial, clinica_id=clinica_id)
    return render(request, "agenda/form.html", _contexto_form(request, form))


@requer_secao("agenda")
def editar(request, pk):
    agendamento = get_object_or_404(Agendamento, pk=pk)
    clinica_id = request.session.get("clinica_id")
    if request.method == "POST":
        form = AgendamentoForm(request.POST, instance=agendamento, clinica_id=clinica_id)
        if form.is_valid():
            ag = _aplicar_form(request, form)
            ag.save()
            messages.success(request, "Agendamento atualizado.")
            return redirect(_voltar(request, _url_agenda("dia", ag.data, _filtros(request))))
    else:
        form = AgendamentoForm(instance=agendamento, clinica_id=clinica_id)
    return render(request, "agenda/form.html", _contexto_form(request, form, agendamento))


# --- Detalhe e ações -----------------------------------------------------------------------

@requer_secao("agenda")
def detalhe(request, pk):
    a = get_object_or_404(Agendamento.objects.select_related("consultorio", "paciente"), pk=pk)
    return render(request, "agenda/_detalhe.html", {
        "a": a, "motivos_cancelamento": Agendamento.MOTIVOS_CANCELAMENTO,
        "voltar": _voltar(request, _url_agenda("dia", a.data, _filtros(request))),
    })


@requer_secao("agenda")
def acao(request, pk):
    a = get_object_or_404(Agendamento, pk=pk)
    voltar = _voltar(request, _url_agenda("dia", a.data, _filtros(request)))
    if request.method != "POST":
        return redirect(voltar)
    acao_pedida = request.POST.get("acao", "")
    motivo = request.POST.get("motivo", "")
    if motivo == "Outro":
        motivo = request.POST.get("motivo_outro", "")
    try:
        msg = services.mudar_status(a, acao_pedida, motivo=motivo, usuario=request.user)
    except services.CancelamentoSemMotivoError as exc:
        messages.error(request, str(exc))
        return redirect(voltar)
    if msg:
        messages.success(request, msg)
    return redirect(voltar)


@requer_secao("agenda")
def mover_view(request, pk):
    """Soltar um bloco arrastado na grade (depois da confirmação na janela)."""
    from datetime import time as _time

    a = get_object_or_404(Agendamento, pk=pk)
    voltar = _voltar(request, _url_agenda("dia", a.data, {}))
    if request.method == "POST":
        try:
            nova_data = date.fromisoformat(request.POST.get("data", ""))
            h, m = (int(x) for x in request.POST.get("hora", "").split(":")[:2])
            consultorio_id = request.POST.get("consultorio", "")
            consultorio = Consultorio.objects.filter(pk=consultorio_id).first() if consultorio_id not in ("", "manter") else None
            services.mover(a, data=nova_data, hora=_time(h, m), consultorio=consultorio,
                           manter_consultorio=consultorio_id == "manter", encaixe=request.POST.get("encaixe") == "1")
            messages.success(request, f"{a.pac_nome} movido para {a.data:%d/%m} às {a.hora:%H:%M}"
                                      + (f" ({a.consultorio.nome})" if a.consultorio else "") + ".")
        except ValueError:
            messages.error(request, "Horário inválido.")
        except services.MoverInvalidoError as exc:
            messages.error(request, str(exc))
    return redirect(voltar)


@requer_secao("agenda")
def reagendar_view(request, pk):
    a = get_object_or_404(Agendamento, pk=pk)
    if request.method == "POST":
        a.data = _data_param(request.POST.get("data"), a.data)
        a.hora = request.POST.get("hora") or a.hora
        a.status = "agendado"
        a.lembrete_enviado_em = None
        a.save(update_fields=["data", "hora", "status", "lembrete_enviado_em"])
        messages.success(request, "Agendamento remarcado.")
    return redirect(_url_agenda("dia", a.data, {}))


@requer_secao("agenda")
def excluir(request, pk):
    a = get_object_or_404(Agendamento, pk=pk)
    voltar = _voltar(request, _url_agenda("dia", a.data, {}))
    if request.method == "POST":
        a.delete()
        messages.success(request, "Agendamento excluído.")
    return redirect(voltar)


# --- Consultórios / fechamento de agenda (admin only) -----------------------

@admin_required
def consultorios_lista(request):
    return render(request, "agenda/consultorios.html", {
        "consultorios": Consultorio.objects.all(),
        "consultorio_form": ConsultorioForm(),
        "bloqueio_form": BloqueioForm(clinica_id=request.session.get("clinica_id")),
        "bloqueios": BloqueioAgenda.objects.filter(
            Q(data_fim__gte=date.today()) | Q(data_fim__isnull=True)
        ).select_related("consultorio"),
    })


@admin_required
def consultorio_salvar(request, pk=None):
    consultorio = get_object_or_404(Consultorio, pk=pk) if pk else None
    if request.method == "POST":
        form = ConsultorioForm(request.POST, instance=consultorio)
        if form.is_valid():
            form.save()
            messages.success(request, "Consultório salvo.")
        else:
            messages.error(request, "Verifique os campos do consultório.")
    return redirect("agenda:consultorios")


@admin_required
def consultorio_excluir(request, pk):
    if request.method == "POST":
        get_object_or_404(Consultorio, pk=pk).delete()
        messages.success(request, "Consultório excluído.")
    return redirect("agenda:consultorios")


@admin_required
def bloqueio_criar(request):
    """"Fechar a agenda" da clínica ou de um consultório (almoço, folga,
    imprevisto) — admin only."""
    if request.method == "POST":
        form = BloqueioForm(request.POST, clinica_id=request.session.get("clinica_id"))
        if form.is_valid():
            bloqueio = form.save(commit=False)
            bloqueio.criado_por_nome = request.user.nome
            bloqueio.save()
            if bloqueio.recorrente:
                fim_txt = f" até {bloqueio.data_fim:%d/%m/%Y}" if bloqueio.data_fim else " (sem data de término)"
                messages.success(
                    request,
                    f"Agenda de {bloqueio.alvo} fechada toda(o) {bloqueio.get_dia_semana_display()} "
                    f"({bloqueio.descricao_faixa()}) a partir de {bloqueio.data_inicio:%d/%m/%Y}{fim_txt}.",
                )
            else:
                messages.success(
                    request,
                    f"Agenda de {bloqueio.alvo} fechada de {bloqueio.data_inicio:%d/%m/%Y} a "
                    f"{bloqueio.data_fim:%d/%m/%Y} ({bloqueio.descricao_faixa()}).",
                )
        else:
            erros = " ".join(e for lista in form.errors.values() for e in lista)
            messages.error(request, erros or "Verifique os campos do bloqueio.")
    return redirect("agenda:consultorios")


@admin_required
def bloqueio_excluir(request, pk):
    """Reabre a agenda pra esse período."""
    if request.method == "POST":
        get_object_or_404(BloqueioAgenda, pk=pk).delete()
        messages.success(request, "Agenda reaberta.")
    return redirect("agenda:consultorios")
