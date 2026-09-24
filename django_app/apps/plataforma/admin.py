from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Clinica, Dominio, LoginAudit, Usuario, UsuarioClinica
from .services import provisionar_clinica


class ProvisionarClinicaForm(forms.Form):
    """Sem campo de senha — o admin da clínica nova recebe um convite por
    e-mail pra definir a própria senha (§5 do plano), mesmo mecanismo usado
    em 🔑 Usuários."""

    nome = forms.CharField(label="Nome da clínica", max_length=200)
    schema_name = forms.SlugField(label="Identificador (schema)", max_length=63)
    admin_nome = forms.CharField(label="Nome do admin da clínica", max_length=150)
    admin_email = forms.EmailField(label="E-mail do admin da clínica")


@admin.register(Clinica)
class ClinicaAdmin(admin.ModelAdmin):
    list_display = ("nome", "schema_name", "plano", "ativa", "criado_em")
    search_fields = ("nome", "schema_name")
    change_list_template = "admin/plataforma/clinica/change_list.html"

    def get_urls(self):
        from django.urls import path

        urls = super().get_urls()
        return [
            path("provisionar/", self.admin_site.admin_view(self.provisionar_view), name="plataforma_clinica_provisionar"),
        ] + urls

    def provisionar_view(self, request):
        from django.shortcuts import redirect, render

        if request.method == "POST":
            form = ProvisionarClinicaForm(request.POST)
            if form.is_valid():
                provisionar_clinica(**form.cleaned_data)
                messages.success(request, "Clínica provisionada com sucesso.")
                return redirect("admin:plataforma_clinica_changelist")
        else:
            form = ProvisionarClinicaForm()
        return render(request, "admin/plataforma/clinica/provisionar.html", {"form": form, "opts": self.model._meta})


@admin.register(Dominio)
class DominioAdmin(admin.ModelAdmin):
    list_display = ("domain", "tenant", "is_primary")


@admin.register(Usuario)
class UsuarioAdmin(DjangoUserAdmin):
    model = Usuario
    list_display = ("email", "nome", "is_active", "is_platform_admin")
    list_filter = ("is_active", "is_platform_admin")
    ordering = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Dados pessoais", {"fields": ("nome",)}),
        ("Permissões", {"fields": ("is_active", "is_platform_admin", "is_superuser", "groups", "user_permissions")}),
        ("Datas", {"fields": ("last_login",)}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "nome", "password1", "password2")}),
    )
    search_fields = ("email", "nome")


@admin.register(UsuarioClinica)
class UsuarioClinicaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "clinica", "papel", "criado_em")
    list_filter = ("papel", "clinica")
    autocomplete_fields = ("usuario", "clinica")


@admin.register(LoginAudit)
class LoginAuditAdmin(admin.ModelAdmin):
    list_display = ("email_tentado", "sucesso", "ip", "criado_em")
    list_filter = ("sucesso",)
    search_fields = ("email_tentado",)
    ordering = ("-criado_em",)
