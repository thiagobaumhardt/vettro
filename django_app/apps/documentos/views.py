from django import forms
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.clickjacking import xframe_options_sameorigin

from apps.core.decorators import admin_required, requer_secao
from apps.pacientes.models import Paciente

from . import services
from .models import DocumentoEmitido, ModeloDocumento


class ModeloDocumentoForm(forms.ModelForm):
    class Meta:
        model = ModeloDocumento
        fields = ["nome", "texto", "ativo"]
        widgets = {"texto": forms.Textarea(attrs={"rows": 18})}


@admin_required  # menu Documentos (lista geral + modelos): só o admin da clínica
@requer_secao("documentos")
def lista(request):
    return render(request, "documentos/lista.html", {
        "modelos": ModeloDocumento.objects.all(),
        "emitidos": DocumentoEmitido.objects.select_related("paciente")[:30],
        "pacientes": Paciente.objects.select_related("tutor").order_by("nome"),
    })


@admin_required
@requer_secao("documentos")
def modelo_salvar(request, pk=None):
    modelo = get_object_or_404(ModeloDocumento, pk=pk) if pk else None
    form = ModeloDocumentoForm(request.POST or None, instance=modelo)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Modelo salvo.")
        return redirect("documentos:lista")
    return render(request, "documentos/modelo_form.html", {
        "form": form, "modelo": modelo, "variaveis": services.VARIAVEIS,
    })


@admin_required
@requer_secao("documentos")
def modelo_excluir(request, pk):
    if request.method == "POST":
        get_object_or_404(ModeloDocumento, pk=pk).delete()
        messages.success(request, "Modelo excluído. Documentos já emitidos foram mantidos.")
    return redirect("documentos:lista")


@requer_secao("documentos")
def emitir(request):
    """GET ?paciente=&modelo= → texto do modelo já preenchido, editável.
    POST → grava o documento com o texto final e abre a pré-visualização."""
    fonte = request.POST if request.method == "POST" else request.GET
    paciente = get_object_or_404(Paciente.objects.select_related("tutor"), pk=fonte.get("paciente"))
    modelo = get_object_or_404(ModeloDocumento, pk=fonte.get("modelo"))

    if request.method == "POST":
        titulo = request.POST.get("titulo", "").strip() or modelo.nome
        texto = request.POST.get("texto", "").strip()
        if texto:
            documento = services.emitir(paciente=paciente, modelo=modelo, titulo=titulo, texto=texto, usuario=request.user)
            messages.success(request, "Documento emitido.")
            return redirect("documentos:detalhe", pk=documento.pk)
        messages.error(request, "O texto do documento não pode ficar vazio.")
    else:
        titulo = modelo.nome
        valores = services.valores_variaveis(
            paciente=paciente, usuario=request.user, clinica_nome=request.session.get("clinica_nome", ""),
        )
        texto = services.preencher(modelo.texto, valores)

    return render(request, "documentos/emitir.html", {
        "paciente": paciente, "modelo": modelo, "titulo": titulo, "texto": texto, "lacuna": services.LACUNA,
    })


@requer_secao("documentos")
def detalhe(request, pk):
    documento = get_object_or_404(DocumentoEmitido.objects.select_related("paciente"), pk=pk)
    return render(request, "documentos/detalhe.html", {"documento": documento})


@xframe_options_sameorigin  # pré-visualização em <iframe> na tela de detalhe
@requer_secao("documentos")
def pdf(request, pk):
    documento = get_object_or_404(DocumentoEmitido, pk=pk)
    conteudo = services.pdf_documento(documento, clinica_nome=request.session.get("clinica_nome", ""))
    resposta = HttpResponse(conteudo, content_type="application/pdf")
    resposta["Content-Disposition"] = f'inline; filename="documento-{documento.criado_em:%Y%m%d}.pdf"'
    return resposta


@admin_required
@requer_secao("documentos")
def excluir(request, pk):
    if request.method == "POST":
        get_object_or_404(DocumentoEmitido, pk=pk).delete()
        messages.success(request, "Documento excluído.")
    return redirect("documentos:lista")
