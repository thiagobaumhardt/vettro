import json
from datetime import date, time

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import requer_secao
from apps.estoque.models import Insumo
from apps.estoque.services import EstoqueInsuficienteError, insumos_para_busca
from apps.financeiro.models import Servico
from apps.financeiro.services import ItemNaoEncontradoError, servicos_do_post
from apps.pacientes.models import ESPECIE_CHOICES
from apps.pacientes.services import usos_insumos_do_post

from . import services
from .forms import AtendimentoForm, VacinaForm
from .models import Atendimento, Vacina

POR_PAGINA = 50
# Quando mandar o lembrete de WhatsApp (dias antes da revacinação/retorno).
OPCOES_LEMBRETE = [(1, "24 horas antes"), (5, "5 dias antes"), (30, "30 dias antes")]
LEMBRETE_PADRAO_DIAS = 5


def _filtrar(atendimentos, params):
    termo = params.get("q", "").strip()
    if termo:
        filtro = Q(pac_nome__icontains=termo) | Q(tutor_nome__icontains=termo) | Q(vacina_nome__icontains=termo)
        if termo.lstrip("#").isdigit():
            filtro |= Q(numero=int(termo.lstrip("#")))
        atendimentos = atendimentos.filter(filtro)
    if params.get("tipo") in Atendimento.Tipo.values:
        atendimentos = atendimentos.filter(tipo=params["tipo"])
    # pac_especie guarda o rótulo ("Cão") em snapshot — filtra por ele pra
    # pegar também atendimentos cujo paciente já foi excluído.
    rotulos_especie = dict(ESPECIE_CHOICES)
    if params.get("especie") in rotulos_especie:
        atendimentos = atendimentos.filter(pac_especie=rotulos_especie[params["especie"]])
    if params.get("de"):
        atendimentos = atendimentos.filter(data__gte=params["de"])
    if params.get("ate"):
        atendimentos = atendimentos.filter(data__lte=params["ate"])
    if params.get("plantao") == "1":
        atendimentos = atendimentos.filter(plantao=True)
    return atendimentos


@requer_secao("atendimentos")
def lista(request):
    atendimentos = _filtrar(
        Atendimento.objects.select_related("retorno_de").order_by("-data", "-hora", "-numero"), request.GET
    )
    pagina = Paginator(atendimentos, POR_PAGINA).get_page(request.GET.get("pagina"))
    filtros = request.GET.copy()
    filtros.pop("pagina", None)
    contexto = {
        "pagina": pagina,
        "filtros": request.GET,
        "filtros_query": filtros.urlencode(),
        "tipos": Atendimento.Tipo.choices,
        "especies": ESPECIE_CHOICES,
    }
    template = "atendimentos/_grid.html" if request.headers.get("HX-Request") else "atendimentos/lista.html"
    return render(request, template, contexto)


def _renderizar_form(request, form):
    servicos = list(Servico.objects.all())
    insumos = list(Insumo.objects.all())
    vacinas = list(Vacina.objects.all())
    anteriores = Atendimento.objects.filter(paciente__isnull=False).order_by("-data", "-hora")
    return render(request, "atendimentos/form.html", {
        "form": form,
        "servicos": servicos,
        "insumos": insumos,
        "servicos_json": json.dumps([{"id": str(s.id), "valor": str(s.valor)} for s in servicos]),
        "insumos_json": json.dumps(insumos_para_busca(insumos)),
        # Opções do campo "Retorno de" — o template filtra pelo paciente escolhido.
        "atendimentos_json": json.dumps([
            {"id": str(a.id), "paciente": str(a.paciente_id), "numero": a.numero,
             "data": a.data.strftime("%d/%m/%Y"), "tipo": a.get_tipo_display()}
            for a in anteriores
        ]),
        "especie_por_paciente_json": json.dumps({str(p.pk): p.especie for p in form.fields["paciente"].queryset}),
        "condicoes_por_paciente_json": json.dumps({
            str(p.pk): [c.nome for c in p.condicoes.all()]
            for p in form.fields["paciente"].queryset.prefetch_related("condicoes")
        }),
        # Protocolo de cada vacina — o template filtra por espécie, limita as
        # doses e sugere a data da próxima (mesma regra de Vacina.sugerir_proxima_dose).
        "vacinas_json": json.dumps([
            {"id": str(v.id), "nome": v.nome, "especie": v.especie, "doses": v.doses_disponiveis(),
             "intervalo": v.intervalo_dias, "reforco": v.reforco_anual,
             "insumo": str(v.insumo_id) if v.insumo_id else None}
            for v in vacinas
        ]),
        "doses_rotulos_json": json.dumps(dict(Atendimento.Dose.choices)),
        # Estado inicial dos campos controlados pelo Alpine — preserva o que
        # foi digitado quando o POST volta com erro.
        "estado_json": json.dumps({
            campo: "" if form[campo].value() is None else form[campo].value()
            for campo in ("tipo", "paciente", "retorno_de", "vacina", "dose", "data", "data_proxima_dose", "data_retorno", "lembrete_dias_antes")
        }, default=str),
        # Aviso na tela quando o lembrete não vai sair (LGPD / módulo desligado).
        "consentimento_whatsapp_json": json.dumps({
            str(p.pk): bool(p.tutor and p.tutor.consentimento_whatsapp and p.tutor.tel)
            for p in form.fields["paciente"].queryset.select_related("tutor")
        }),
        "whatsapp_habilitado": "lembretes" in (request.session.get("modulos_habilitados") or []),
        "lembrete_padrao_dias": LEMBRETE_PADRAO_DIAS,
        "opcoes_lembrete": OPCOES_LEMBRETE,
        "voltar": request.POST.get("voltar") or request.GET.get("voltar", ""),
    })


@requer_secao("atendimentos")
def novo(request):
    """GET aceita ?paciente=&tipo= (vindo dos botões da Ficha do paciente) e
    ?voltar=paciente pra retornar ao histórico dele depois de salvar."""
    if request.method != "POST" and request.GET.get("tipo") not in Atendimento.Tipo.values:
        # Sem tipo escolhido: hub "que tipo de atendimento é?".
        from apps.pacientes.models import Paciente

        return render(request, "atendimentos/hub.html", {
            "pacientes": Paciente.objects.select_related("tutor").order_by("nome"),
            "paciente_inicial": request.GET.get("paciente", ""),
        })
    if request.method != "POST":
        inicial = {"data": date.today(), "hora": time(9, 0), "lembrete_dias_antes": LEMBRETE_PADRAO_DIAS}
        if request.GET.get("tipo") in Atendimento.Tipo.values:
            inicial["tipo"] = request.GET["tipo"]
        if request.GET.get("paciente"):
            inicial["paciente"] = request.GET["paciente"]
        return _renderizar_form(request, AtendimentoForm(initial=inicial))

    form = AtendimentoForm(request.POST)
    if not form.is_valid():
        campos = ("retorno_de", "vacina", "dose", "data_proxima_dose", "data_retorno", "lembrete_dias_antes")
        erros = next((form.errors[c][0] for c in campos if c in form.errors), None)
        messages.error(request, erros or "Verifique os campos do formulário.")
        return _renderizar_form(request, form)
    dados = form.cleaned_data
    try:
        atendimento = services.criar_atendimento(
            paciente=dados["paciente"], tipo=dados["tipo"], retorno_de=dados["retorno_de"],
            vacina=dados["vacina"], dose=dados["dose"], data_proxima_dose=dados["data_proxima_dose"],
            data_retorno=dados["data_retorno"], lembrete_dias_antes=dados["lembrete_dias_antes"],
            data=dados["data"], hora=dados["hora"], servico_ids=servicos_do_post(request.POST),
            usos_insumos=usos_insumos_do_post(request.POST), plantao=dados["plantao"],
            obs=dados["obs"], usuario=request.user,
        )
    except (EstoqueInsuficienteError, ItemNaoEncontradoError) as exc:
        messages.error(request, str(exc))
        return _renderizar_form(request, form)
    messages.success(request, f"Atendimento #{atendimento.numero} registrado.")
    if request.POST.get("voltar") == "paciente":
        return redirect(reverse("pacientes:ficha", args=[atendimento.paciente_id]) + "?aba=historico")
    return redirect("atendimentos:lista")


@requer_secao("atendimentos")
def excluir(request, pk):
    if request.method == "POST":
        tinha_paga = services.excluir_atendimento(get_object_or_404(Atendimento, pk=pk), usuario=request.user)
        messages.success(request, "Atendimento excluído. Insumos devolvidos ao estoque.")
        if tinha_paga:
            messages.warning(request, "A cobrança deste atendimento já estava paga e foi mantida — faça o reembolso, se for o caso.")
    return redirect("atendimentos:lista")


def _renderizar_vacinas(request, form=None, editando=None):
    return render(request, "atendimentos/vacinas.html", {
        "vacinas": Vacina.objects.select_related("insumo").all(),
        "form": form or VacinaForm(),
        "editando": editando,
    })


@requer_secao("atendimentos")
def vacinas(request):
    return _renderizar_vacinas(request)


@requer_secao("atendimentos")
def vacina_salvar(request, pk=None):
    vacina = get_object_or_404(Vacina, pk=pk) if pk else None
    if request.method == "POST":
        form = VacinaForm(request.POST, instance=vacina)
        if form.is_valid():
            form.save()
            messages.success(request, "Vacina salva.")
            return redirect("atendimentos:vacinas")
        return _renderizar_vacinas(request, form=form, editando=vacina)
    return _renderizar_vacinas(request, form=VacinaForm(instance=vacina), editando=vacina)


@requer_secao("atendimentos")
def vacina_excluir(request, pk):
    if request.method == "POST":
        get_object_or_404(Vacina, pk=pk).delete()
        messages.success(request, "Vacina excluída. O histórico de aplicações foi mantido.")
    return redirect("atendimentos:vacinas")
