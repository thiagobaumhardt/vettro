import json
from datetime import date, time

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import requer_secao
from apps.estoque.models import Insumo
from apps.estoque.services import EstoqueInsuficienteError
from apps.financeiro.models import Servico
from apps.financeiro.services import ItemNaoEncontradoError
from apps.pacientes.services import usos_insumos_do_post

from . import services
from .forms import AtendimentoForm
from .models import Atendimento


@requer_secao("atendimentos")
def lista(request):
    servicos = list(Servico.objects.all())
    insumos = list(Insumo.objects.all())
    contexto = {
        "atendimentos": Atendimento.objects.select_related("paciente").all(),
        "form": AtendimentoForm(initial={"data": date.today(), "hora": time(9, 0)}),
        "servicos": servicos,
        "insumos": insumos,
        "servicos_json": json.dumps([{"id": str(s.id), "valor": str(s.valor)} for s in servicos]),
        "insumos_json": json.dumps([{"id": str(i.id), "valor": str(i.valor)} for i in insumos]),
    }
    return render(request, "atendimentos/lista.html", contexto)


@requer_secao("atendimentos")
def criar(request):
    form = AtendimentoForm(request.POST)
    if form.is_valid():
        try:
            services.criar_atendimento(
                paciente=form.cleaned_data["paciente"], data=form.cleaned_data["data"],
                hora=form.cleaned_data["hora"], servico_ids=request.POST.getlist("servico_ids"),
                usos_insumos=usos_insumos_do_post(request.POST), plantao=form.cleaned_data["plantao"],
                obs=form.cleaned_data["obs"], usuario=request.user,
            )
            messages.success(request, "Atendimento registrado.")
        except (EstoqueInsuficienteError, ItemNaoEncontradoError) as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Verifique os campos do formulário.")
    return redirect("atendimentos:lista")


@requer_secao("atendimentos")
def excluir(request, pk):
    if request.method == "POST":
        get_object_or_404(Atendimento, pk=pk).delete()
        messages.success(request, "Atendimento excluído.")
    return redirect("atendimentos:lista")
