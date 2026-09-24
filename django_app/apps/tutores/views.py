import requests
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.http import JsonResponse

from apps.auditoria.services import ip_da_requisicao, registrar as registrar_auditoria
from apps.core.decorators import admin_required, requer_secao
from apps.pacientes.models import Paciente

from . import services
from .forms import TutorForm
from .models import Tutor


@requer_secao("tutores")
def lista(request):
    termo = request.GET.get("q", "").strip()
    tutores = Tutor.objects.all()
    if termo:
        tutores = tutores.filter(Q(nome__icontains=termo) | Q(tel__icontains=termo))

    contexto = {"tutores": tutores, "termo": termo}
    template = "tutores/_lista_resultado.html" if request.headers.get("HX-Request") else "tutores/lista.html"
    return render(request, template, contexto)


@requer_secao("tutores")
def form_view(request, pk=None):
    tutor = get_object_or_404(Tutor, pk=pk) if pk else None

    consentimento_anterior = tutor.consentimento_dados if tutor else False

    if request.method == "POST":
        form = TutorForm(request.POST, instance=tutor)
        if form.is_valid():
            era_novo = tutor is None
            novo = form.save(commit=False)
            services.salvar_consentimento(novo, consentimento_anterior, form.cleaned_data["consentimento_dados"])
            novo.save()
            registrar_auditoria(
                usuario=request.user, acao="criar" if era_novo else "atualizar",
                entidade="tutor", entidade_id=novo.id, detalhe=novo.nome, ip=ip_da_requisicao(request),
            )
            messages.success(request, "Tutor salvo com sucesso.")
            return redirect("tutores:lista")
    else:
        form = TutorForm(instance=tutor)

    return render(request, "tutores/form.html", {"form": form, "tutor": tutor})


@requer_secao("tutores")
def detalhe(request, pk):
    tutor = get_object_or_404(Tutor, pk=pk)
    pacientes = Paciente.objects.filter(tutor=tutor)
    return render(request, "tutores/detalhe.html", {"tutor": tutor, "pacientes": pacientes})


@requer_secao("tutores")
def excluir(request, pk):
    tutor = get_object_or_404(Tutor, pk=pk)
    if request.method == "POST":
        nome, tutor_id = tutor.nome, tutor.id
        tutor.delete()
        registrar_auditoria(
            usuario=request.user, acao="excluir", entidade="tutor",
            entidade_id=tutor_id, detalhe=nome, ip=ip_da_requisicao(request),
        )
        messages.success(request, "Tutor excluído.")
        return redirect("tutores:lista")
    return redirect("tutores:detalhe", pk=pk)


@requer_secao("tutores")
def cep_lookup(request):
    """Proxy server-side pro ViaCEP (§7 do plano) — dispara em hx-get no blur
    do campo CEP, resposta troca os campos de endereço via OOB swap."""
    cep = "".join(filter(str.isdigit, request.GET.get("cep", "")))
    dados = {}
    if len(cep) == 8:
        try:
            resposta = requests.get(f"https://viacep.com.br/ws/{cep}/json/", timeout=4)
            corpo = resposta.json()
            if not corpo.get("erro"):
                dados = corpo
        except requests.RequestException:
            pass
    return render(request, "tutores/_cep_resultado.html", {"dados": dados})


@admin_required
def exportar_dados(request, pk):
    """Exportação LGPD (admin only) — HttpResponse com Content-Disposition,
    substitui o hack de Blob+<a download> do Vue (§7 do plano)."""
    tutor = get_object_or_404(Tutor, pk=pk)
    payload = services.dados_exportacao_lgpd(tutor)
    resposta = JsonResponse(payload, json_dumps_params={"ensure_ascii": False, "indent": 2})
    nome_arquivo = f"vettro-dados-{tutor.nome.lower().replace(' ', '-')}.json"
    resposta["Content-Disposition"] = f'attachment; filename="{nome_arquivo}"'
    registrar_auditoria(
        usuario=request.user, acao="exportar", entidade="tutor",
        entidade_id=tutor.id, detalhe=tutor.nome, ip=ip_da_requisicao(request),
    )
    return resposta
