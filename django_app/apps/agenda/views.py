import calendar
import json
from datetime import date, timedelta

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

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


def _contexto_calendario(ano: int, mes: int, dia_selecionado: date, consultorio_id: str = ""):
    cal = calendar.Calendar(firstweekday=6)  # domingo primeiro
    semanas = cal.monthdayscalendar(ano, mes)

    agendamentos_mes = Agendamento.objects.filter(data__year=ano, data__month=mes).exclude(status="cancelado")
    do_dia = Agendamento.objects.filter(data=dia_selecionado)
    proximos_qs = Agendamento.objects.filter(data__gte=date.today()).exclude(status="cancelado")
    if consultorio_id:
        agendamentos_mes = agendamentos_mes.filter(consultorio_id=consultorio_id)
        do_dia = do_dia.filter(consultorio_id=consultorio_id)
        proximos_qs = proximos_qs.filter(consultorio_id=consultorio_id)

    dias_com_evento = {d.isoformat() for d in agendamentos_mes.values_list("data", flat=True)}

    dias_bloqueados = set()
    if consultorio_id:
        for bloqueio in BloqueioAgenda.objects.filter(
            consultorio_id=consultorio_id, data_fim__gte=date(ano, mes, 1),
            data_inicio__lte=date(ano, mes, calendar.monthrange(ano, mes)[1]),
        ):
            d = max(bloqueio.data_inicio, date(ano, mes, 1))
            fim = min(bloqueio.data_fim, date(ano, mes, calendar.monthrange(ano, mes)[1]))
            while d <= fim:
                dias_bloqueados.add(d.isoformat())
                d += timedelta(days=1)

    hoje = date.today()
    return {
        "ano": ano, "mes": mes, "mes_nome": MESES_PT[mes],
        "semanas": semanas, "dias_com_evento": dias_com_evento, "dias_bloqueados": dias_bloqueados,
        "dia_selecionado_iso": dia_selecionado.isoformat(),
        "dia_selecionado": dia_selecionado, "hoje": hoje,
        "do_dia": do_dia.order_by("hora"), "proximos": proximos_qs.order_by("data", "hora")[:8],
        "consultorio_id": consultorio_id,
        "dia_bloqueado_selecionado": dia_selecionado.isoformat() in dias_bloqueados,
    }


@requer_secao("agenda")
def calendario(request):
    hoje = date.today()
    ano = int(request.GET.get("ano", hoje.year))
    mes = int(request.GET.get("mes", hoje.month))
    dia_str = request.GET.get("dia")
    dia_selecionado = date.fromisoformat(dia_str) if dia_str else hoje
    consultorio_id = request.GET.get("consultorio", "")

    pacientes = list(Paciente.objects.select_related("tutor").all())
    contexto = _contexto_calendario(ano, mes, dia_selecionado, consultorio_id)
    contexto.update({
        "form": AgendamentoForm(initial={"data": dia_selecionado}),
        "servicos": Servico.objects.all(),
        "consultorios": Consultorio.objects.filter(ativo=True),
        "pacientes_json": json.dumps([
            {"id": str(p.id), "nome": p.nome, "tutor_nome": p.tutor.nome if p.tutor else "",
             "tutor_tel": p.tutor.tel if p.tutor else ""}
            for p in pacientes
        ]),
    })

    if request.headers.get("HX-Request"):
        return render(request, "agenda/_calendario_swap.html", contexto)
    return render(request, "agenda/calendario.html", contexto)


@requer_secao("agenda")
def form_view(request, pk=None):
    agendamento = get_object_or_404(Agendamento, pk=pk) if pk else None

    if request.method == "POST":
        form = AgendamentoForm(request.POST, instance=agendamento)
        if form.is_valid():
            resolvido = services.resolver_paciente(
                paciente=form.cleaned_data["paciente"], pac_nome=form.cleaned_data["pac_nome"],
                tutor_nome=form.cleaned_data["tutor_nome"], tutor_tel=form.cleaned_data["tutor_tel"],
            )
            novo = form.save(commit=False)
            novo.paciente = resolvido["paciente"]
            novo.pac_nome = resolvido["pac_nome"]
            novo.tutor_nome = resolvido["tutor_nome"]
            novo.tutor_tel = resolvido["tutor_tel"]
            novo.servicos = [
                {"id": str(s.id), "nome": s.nome, "valor": str(s.valor)}
                for s in Servico.objects.filter(pk__in=request.POST.getlist("servico_ids"))
            ]
            novo.save()
            messages.success(request, "Agendamento salvo.")
            return redirect(f"/agenda/?ano={novo.data.year}&mes={novo.data.month}&dia={novo.data.isoformat()}")
        else:
            erros = " ".join(e for lista in form.errors.values() for e in lista)
            messages.error(request, erros or "Não foi possível salvar o agendamento.")

    return redirect("agenda:calendario")


@requer_secao("agenda")
def status_view(request, pk):
    if request.method == "POST":
        agendamento = get_object_or_404(Agendamento, pk=pk)
        novo_status = request.POST.get("status")
        if novo_status in dict(Agendamento.STATUS_CHOICES):
            agendamento.status = novo_status
            agendamento.save(update_fields=["status"])
    return redirect("agenda:calendario")


@requer_secao("agenda")
def reagendar_view(request, pk):
    if request.method == "POST":
        agendamento = get_object_or_404(Agendamento, pk=pk)
        agendamento.data = request.POST.get("data") or agendamento.data
        agendamento.hora = request.POST.get("hora") or agendamento.hora
        agendamento.status = "agendado"
        agendamento.save(update_fields=["data", "hora", "status"])
        return redirect(f"/agenda/?ano={agendamento.data.year}&mes={agendamento.data.month}&dia={agendamento.data.isoformat()}")
    return redirect("agenda:calendario")


@requer_secao("agenda")
def excluir(request, pk):
    if request.method == "POST":
        get_object_or_404(Agendamento, pk=pk).delete()
        messages.success(request, "Agendamento excluído.")
    return redirect("agenda:calendario")


# --- Consultórios / fechamento de agenda (admin only) -----------------------

@admin_required
def consultorios_lista(request):
    return render(request, "agenda/consultorios.html", {
        "consultorios": Consultorio.objects.all(),
        "consultorio_form": ConsultorioForm(),
        "bloqueio_form": BloqueioForm(),
        "bloqueios": BloqueioAgenda.objects.filter(data_fim__gte=date.today()).select_related("consultorio"),
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
    """"Fechar a agenda" de um consultório num período — pedido explícito do
    usuário, admin only."""
    if request.method == "POST":
        form = BloqueioForm(request.POST)
        if form.is_valid():
            bloqueio = form.save(commit=False)
            bloqueio.criado_por_nome = request.user.nome
            bloqueio.save()
            messages.success(
                request,
                f"Agenda de {bloqueio.consultorio.nome} fechada de "
                f"{bloqueio.data_inicio:%d/%m/%Y} a {bloqueio.data_fim:%d/%m/%Y}.",
            )
        else:
            messages.error(request, "Verifique os campos do bloqueio.")
    return redirect("agenda:consultorios")


@admin_required
def bloqueio_excluir(request, pk):
    """Reabre a agenda do consultório pra esse período."""
    if request.method == "POST":
        get_object_or_404(BloqueioAgenda, pk=pk).delete()
        messages.success(request, "Agenda reaberta.")
    return redirect("agenda:consultorios")
