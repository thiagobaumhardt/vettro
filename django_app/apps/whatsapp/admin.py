from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path

from apps.plataforma.models import Clinica

from . import services
from .meta import ErroWhatsApp
from .models import ConexaoWhatsApp


class ConectarManualForm(forms.Form):
    """Conexão sem o Embedded Signup — WABA, número e token de system user
    gerados à mão no portfólio de negócios da clínica. É o caminho da fase 1
    (só a Lume, sem Tech Provider); passo a passo em docs/whatsapp-meta.md."""

    clinica = forms.ModelChoiceField(label="Clínica", queryset=Clinica.objects.exclude(schema_name="public"))
    waba_id = forms.CharField(label="ID da conta WhatsApp Business (WABA)", max_length=64)
    phone_number_id = forms.CharField(label="ID do número", max_length=64)
    token = forms.CharField(label="Token de acesso (system user)", widget=forms.PasswordInput)
    registrar = forms.BooleanField(
        label="Registrar o número na Cloud API", required=False,
        help_text="Marque se o número é novo e ainda não foi registrado (gera um PIN de 2 etapas).",
    )


@admin.register(ConexaoWhatsApp)
class ConexaoWhatsAppAdmin(admin.ModelAdmin):
    list_display = ("clinica", "numero_exibicao", "nome_exibicao", "status", "coexistencia", "atualizado_em")
    readonly_fields = (
        "clinica", "waba_id", "phone_number_id", "numero_exibicao", "nome_exibicao", "qualidade",
        "coexistencia", "status", "erro", "modelos", "conectado_em", "atualizado_em",
    )
    exclude = ("token_cifrado", "pin_cifrado")
    change_list_template = "admin/whatsapp/conexaowhatsapp/change_list.html"
    actions = ["sincronizar", "desconectar"]

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        return [
            path("conectar/", self.admin_site.admin_view(self.conectar_view), name="whatsapp_conexaowhatsapp_conectar"),
        ] + super().get_urls()

    def conectar_view(self, request):
        form = ConectarManualForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            dados = form.cleaned_data
            try:
                services.conectar_manual(
                    dados["clinica"], waba_id=dados["waba_id"], phone_number_id=dados["phone_number_id"],
                    token=dados["token"], registrar=dados["registrar"],
                )
            except ErroWhatsApp as exc:
                messages.error(request, f"Não foi possível conectar: {exc}")
            else:
                messages.success(request, "WhatsApp conectado e modelos enviados para aprovação.")
                return redirect("admin:whatsapp_conexaowhatsapp_changelist")
        return render(request, "admin/whatsapp/conexaowhatsapp/conectar.html", {"form": form, "opts": self.model._meta})

    @admin.action(description="Atualizar número e modelos")
    def sincronizar(self, request, queryset):
        for conexao in queryset:
            try:
                services.atualizar_dados_numero(conexao)
                services.sincronizar_modelos(conexao)
            except ErroWhatsApp as exc:
                messages.error(request, f"{conexao.clinica}: {exc}")

    @admin.action(description="Desconectar")
    def desconectar(self, request, queryset):
        for conexao in queryset:
            services.desconectar(conexao)
