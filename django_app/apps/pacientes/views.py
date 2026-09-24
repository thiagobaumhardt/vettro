import json

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.auditoria.services import ip_da_requisicao, registrar as registrar_auditoria
from apps.core.decorators import admin_required, requer_secao, secoes_permitidas
from apps.estoque.models import Insumo
from apps.estoque.services import EstoqueInsuficienteError
from apps.financeiro.models import Cobranca, CirurgiaCategoria, Servico
from apps.financeiro.services import ItemNaoEncontradoError
from apps.tutores.models import Tutor

from . import services as pacientes_services
from .forms import AnamneseForm, CirurgiaForm, NotaForm, PacienteForm
from .models import AnamneseHist, CirurgiaHist, Exame, Foto, Nota, Paciente
from .racas import RACAS_POR_ESPECIE

ABAS_DISPONIVEIS = {"ficha", "notas", "anamnese", "cirurgias", "exames", "fotos", "cobranca"}
ABAS_ADMIN_ONLY = {"cobranca"}
ABAS_CLINICAS = {"anamnese", "cirurgias", "exames", "fotos"}  # exige seção "pacientes_clinico"


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
        or (aba in ABAS_CLINICAS and "pacientes_clinico" not in secoes_permitidas(papel))
    ):
        aba = "ficha"

    contexto = {"paciente": paciente, "aba_ativa": aba}
    if aba == "notas":
        contexto.update(notas=paciente.notas.all(), form=NotaForm())
    elif aba == "anamnese":
        contexto.update(_contexto_anamnese(paciente))
    elif aba == "cirurgias":
        contexto.update(_contexto_cirurgias(paciente))
    elif aba == "exames":
        contexto.update(exames=paciente.exames.all())
    elif aba == "fotos":
        contexto.update(fotos=paciente.fotos.all())
    elif aba == "cobranca":
        contexto.update(_contexto_cobranca(paciente))

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
    if aba in ABAS_CLINICAS and "pacientes_clinico" not in secoes_permitidas(papel):
        raise PermissionDenied("Seu perfil não tem acesso a dados clínicos.")

    if aba == "ficha":
        return render(request, "pacientes/ficha/_ficha_info.html", {"paciente": paciente})

    if aba == "notas":
        notas = paciente.notas.all()
        return render(request, "pacientes/ficha/_ficha_notas.html", {
            "paciente": paciente, "notas": notas, "form": NotaForm(),
        })

    if aba == "cobranca":
        return render(request, "pacientes/ficha/_ficha_cobranca.html", _contexto_cobranca(paciente))

    if aba == "anamnese":
        return render(request, "pacientes/ficha/_ficha_anamnese.html", _contexto_anamnese(paciente))

    if aba == "cirurgias":
        return render(request, "pacientes/ficha/_ficha_cirurgias.html", _contexto_cirurgias(paciente))

    if aba == "exames":
        return render(request, "pacientes/ficha/_ficha_exames.html", {
            "paciente": paciente, "exames": paciente.exames.all(),
        })

    if aba == "fotos":
        return render(request, "pacientes/ficha/_ficha_fotos.html", {
            "paciente": paciente, "fotos": paciente.fotos.all(),
        })


def _contexto_anamnese(paciente, erro=None):
    servicos = list(Servico.objects.all())
    insumos = list(Insumo.objects.all())
    return {
        "paciente": paciente, "form": AnamneseForm(),
        "servicos": servicos, "insumos": insumos,
        "servicos_json": json.dumps([{"id": str(s.id), "valor": str(s.valor)} for s in servicos]),
        "insumos_json": json.dumps([{"id": str(i.id), "valor": str(i.valor)} for i in insumos]),
        "historico": paciente.anamneses.all(), "erro": erro,
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
            {"id": str(c.id), "valor": str(valor_por_peso(c, paciente.peso))} for c in categorias
        ]),
        "insumos_json": json.dumps([{"id": str(i.id), "valor": str(i.valor)} for i in insumos]),
        "historico": paciente.cirurgias.all(), "erro": erro,
        "faixa_peso_label": _faixa_peso_label(paciente.peso),
    }


def _contexto_cobranca(paciente, erro=None):
    servicos = list(Servico.objects.all())
    insumos = list(Insumo.objects.all())
    return {
        "paciente": paciente, "servicos": servicos, "insumos": insumos,
        "servicos_json": json.dumps([{"id": str(s.id), "valor": str(s.valor)} for s in servicos]),
        "insumos_json": json.dumps([{"id": str(i.id), "valor": str(i.valor)} for i in insumos]),
        "historico": paciente.cobrancas.all(), "erro": erro,
    }


@admin_required
def cobranca_criar(request, pk):
    """Cobrança manual — mesmo padrão de montar_servicos/montar_insumos de
    Anamnese/Cirurgia, mas sem campos clínicos (porte de
    backend/app/routers/cobrancas.py, admin only)."""
    paciente = get_object_or_404(Paciente, pk=pk)
    servico_ids = request.POST.getlist("servico_ids")
    usos_insumos = pacientes_services.usos_insumos_do_post(request.POST)
    obs = request.POST.get("obs", "")

    if not servico_ids and not usos_insumos:
        return render(request, "pacientes/ficha/_ficha_cobranca.html", {
            **_contexto_cobranca(paciente), "erro": "Selecione ao menos um serviço ou insumo.",
        })

    try:
        from apps.financeiro import services as financeiro_services
        from apps.estoque.services import debitar_para_consumo

        servicos_itens, total_servicos = financeiro_services.montar_servicos(servico_ids)
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
        Cobranca.objects.filter(pk=cobranca_id, paciente=paciente).delete()
    return render(request, "pacientes/ficha/_ficha_cobranca.html", _contexto_cobranca(paciente))


def _faixa_peso_label(peso):
    if not peso:
        return None
    if peso < 10:
        return f"⚖️ Faixa: até 10kg ({peso} kg)"
    if peso <= 25:
        return f"⚖️ Faixa: 10–25kg ({peso} kg)"
    return f"⚖️ Faixa: acima de 25kg ({peso} kg)"


@requer_secao("pacientes_clinico")
def anamnese_criar(request, pk):
    paciente = get_object_or_404(Paciente, pk=pk)
    form = AnamneseForm(request.POST)
    if form.is_valid():
        try:
            pacientes_services.criar_anamnese(
                paciente=paciente, dados_clinicos=form.cleaned_data,
                servico_ids=request.POST.getlist("servico_ids"),
                usos_insumos=pacientes_services.usos_insumos_do_post(request.POST),
                plantao=request.POST.get("plantao") == "on",
                usuario=request.user,
            )
            messages.success(request, "Anamnese registrada. Cobrança gerada automaticamente, se aplicável.")
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
        AnamneseHist.objects.filter(pk=anamnese_id, paciente=paciente).delete()
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
        CirurgiaHist.objects.filter(pk=cirurgia_id, paciente=paciente).delete()
    return render(request, "pacientes/ficha/_ficha_cirurgias.html", _contexto_cirurgias(paciente))


@requer_secao("pacientes_clinico")
def exame_upload(request, pk):
    paciente = get_object_or_404(Paciente, pk=pk)
    if request.method == "POST":
        for arquivo in request.FILES.getlist("arquivos"):
            if not arquivo.name.lower().endswith(".pdf"):
                messages.error(request, f"{arquivo.name} não é um PDF e foi ignorado.")
                continue
            Exame.objects.create(paciente=paciente, nome=arquivo.name, arquivo=arquivo)
    return render(request, "pacientes/ficha/_ficha_exames.html", {"paciente": paciente, "exames": paciente.exames.all()})


@requer_secao("pacientes_clinico")
def exame_excluir(request, pk, exame_id):
    paciente = get_object_or_404(Paciente, pk=pk)
    if request.method == "POST":
        Exame.objects.filter(pk=exame_id, paciente=paciente).delete()
    return render(request, "pacientes/ficha/_ficha_exames.html", {"paciente": paciente, "exames": paciente.exames.all()})


@requer_secao("pacientes_clinico")
def foto_upload(request, pk):
    paciente = get_object_or_404(Paciente, pk=pk)
    if request.method == "POST":
        for arquivo in request.FILES.getlist("arquivos"):
            if not arquivo.content_type.startswith("image/"):
                continue
            Foto.objects.create(paciente=paciente, nome=arquivo.name, imagem=arquivo)
    return render(request, "pacientes/ficha/_ficha_fotos.html", {"paciente": paciente, "fotos": paciente.fotos.all()})


@requer_secao("pacientes_clinico")
def foto_excluir(request, pk, foto_id):
    paciente = get_object_or_404(Paciente, pk=pk)
    if request.method == "POST":
        Foto.objects.filter(pk=foto_id, paciente=paciente).delete()
    return render(request, "pacientes/ficha/_ficha_fotos.html", {"paciente": paciente, "fotos": paciente.fotos.all()})


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
