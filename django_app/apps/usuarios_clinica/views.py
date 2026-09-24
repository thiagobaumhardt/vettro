from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import admin_required
from apps.plataforma.convites import enviar_convite, enviar_notificacao_novo_acesso
from apps.plataforma.models import Usuario, UsuarioClinica

from .forms import AdicionarUsuarioForm, PapelForm


def _clinica_id(request):
    return request.session["clinica_id"]


@admin_required
def lista(request):
    vinculos = UsuarioClinica.objects.filter(clinica_id=_clinica_id(request)).select_related("usuario")
    return render(request, "usuarios_clinica/lista.html", {
        "vinculos": vinculos, "form": AdicionarUsuarioForm(),
    })


@admin_required
def adicionar(request):
    if request.method == "POST":
        form = AdicionarUsuarioForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            clinica_nome = request.session.get("clinica_nome", "")
            era_novo = not form.cleaned_data["usuario_existente"]

            if era_novo:
                usuario = Usuario(email=email, nome=form.cleaned_data["nome"])
                usuario.set_unusable_password()
                usuario.save()
            else:
                usuario = Usuario.objects.get(email=email)

            vinculo, criado = UsuarioClinica.objects.get_or_create(
                usuario=usuario, clinica_id=_clinica_id(request),
                defaults={"papel": form.cleaned_data["papel"]},
            )

            if not criado:
                messages.info(request, f"{usuario.email} já tinha acesso a esta clínica.")
            elif era_novo:
                enviar_convite(usuario, clinica_nome)
                messages.success(request, f"{usuario.email} adicionado(a) — convite enviado por e-mail pra definir a senha.")
            else:
                enviar_notificacao_novo_acesso(usuario, clinica_nome)
                messages.success(request, f"{usuario.email} adicionado(a) à clínica (conta já existente reaproveitada).")
        else:
            erros = " ".join(e for lista_erros in form.errors.values() for e in lista_erros)
            messages.error(request, erros or "Não foi possível adicionar.")
    return redirect("usuarios_clinica:lista")


@admin_required
def alterar_papel(request, vinculo_id):
    vinculo = get_object_or_404(UsuarioClinica, pk=vinculo_id, clinica_id=_clinica_id(request))
    if request.method == "POST":
        form = PapelForm(request.POST)
        if form.is_valid():
            vinculo.papel = form.cleaned_data["papel"]
            vinculo.save(update_fields=["papel"])
            messages.success(request, "Papel atualizado.")
    return redirect("usuarios_clinica:lista")


@admin_required
def remover(request, vinculo_id):
    """Remove o vínculo só DESTA clínica — não mexe na conta global nem no
    acesso a outras clínicas que essa pessoa tenha (§5 do plano)."""
    if request.method == "POST":
        vinculo = get_object_or_404(UsuarioClinica, pk=vinculo_id, clinica_id=_clinica_id(request))
        email = vinculo.usuario.email
        vinculo.delete()
        messages.success(request, f"Acesso de {email} a esta clínica removido.")
    return redirect("usuarios_clinica:lista")
