from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin

from apps.core.decorators import requer_secao
from apps.core.models import PerfilProfissional
from apps.pacientes.models import Paciente

from . import services
from .models import FARMACIA_CHOICES, USO_CHOICES, Receita


def _renderizar_form(request, paciente, tipo, *, texto="", itens=None):
    return render(request, "receitas/form.html", {
        "paciente": paciente, "tipo": tipo, "tipo_rotulo": Receita.Tipo(tipo).label,
        "texto": texto, "itens": itens or [{}],
        "usos": USO_CHOICES, "farmacias": FARMACIA_CHOICES,
        "perfil": PerfilProfissional.de(request.user),
    })


@requer_secao("pacientes_clinico")
def nova(request, pk):
    paciente = get_object_or_404(Paciente.objects.select_related("tutor"), pk=pk)
    tipo = request.POST.get("tipo") or request.GET.get("tipo")
    if tipo not in Receita.Tipo.values:
        raise Http404
    if request.method != "POST":
        return _renderizar_form(request, paciente, tipo)

    texto = request.POST.get("texto", "").strip()
    itens_brutos = [
        dict(zip(services.CAMPOS_ITEM, valores))
        for valores in zip(*[request.POST.getlist(f"item_{c}") for c in services.CAMPOS_ITEM])
    ]
    try:
        if tipo == Receita.Tipo.LIVRE:
            if not texto:
                raise services.ReceitaInvalidaError("Digite o texto da receita.")
            itens = []
        else:
            itens = services.itens_do_post(request.POST)
        if tipo == Receita.Tipo.CONTROLADA and len(itens) > 1:
            raise services.ReceitaInvalidaError("Receita controlada só pode ter 1 medicamento — faça uma receita para cada.")
        if tipo == Receita.Tipo.CONTROLADA and not PerfilProfissional.de(request.user).crmv:
            raise services.ReceitaInvalidaError("Receita controlada exige seu CRMV — preencha em Meu perfil.")
    except services.ReceitaInvalidaError as exc:
        messages.error(request, str(exc))
        return _renderizar_form(request, paciente, tipo, texto=texto, itens=itens_brutos)

    receita = services.criar_receita(paciente=paciente, tipo=tipo, texto=texto, itens=itens, usuario=request.user)
    messages.success(request, f"{receita.get_tipo_display()} salva.")
    return redirect("receitas:detalhe", pk=paciente.pk, receita_id=receita.pk)


@requer_secao("pacientes_clinico")
def detalhe(request, pk, receita_id):
    receita = get_object_or_404(Receita.objects.select_related("paciente"), pk=receita_id, paciente_id=pk)
    return render(request, "receitas/detalhe.html", {"receita": receita, "paciente": receita.paciente})


@xframe_options_sameorigin  # pré-visualização em <iframe> na tela de detalhe
@requer_secao("pacientes_clinico")
def pdf(request, pk, receita_id):
    receita = get_object_or_404(Receita, pk=receita_id, paciente_id=pk)
    conteudo = services.pdf_receita(
        receita, clinica_nome=request.session.get("clinica_nome", ""),
        impresso_por=getattr(request.user, "nome", "") or request.user.get_username(),
    )
    resposta = HttpResponse(conteudo, content_type="application/pdf")
    resposta["Content-Disposition"] = f'inline; filename="receita-{receita.pac_nome}-{receita.criado_em:%Y%m%d}.pdf"'
    return resposta


@requer_secao("pacientes_clinico")
def excluir(request, pk, receita_id):
    if request.method == "POST":
        get_object_or_404(Receita, pk=receita_id, paciente_id=pk).delete()
        messages.success(request, "Receita excluída.")
    return redirect(reverse("pacientes:ficha", args=[pk]) + "?aba=receitas")
