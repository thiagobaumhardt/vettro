from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .campos import TelefoneField
from .decorators import admin_required
from .models import ConfiguracaoClinica, PerfilProfissional
from .validators import cnpj_valido, formatar_cnpj


def health(request):
    return JsonResponse({"status": "ok"})


class ConfiguracaoClinicaForm(forms.ModelForm):
    telefone = TelefoneField(required=False)

    class Meta:
        model = ConfiguracaoClinica
        fields = [
            "razao_social", "cnpj", "telefone", "email",
            "cep", "endereco", "numero", "complemento", "bairro", "cidade", "uf",
            "regime_tributario", "cfop_venda", "cst_csosn_venda", "cfop_venda_st", "cst_csosn_venda_st",
            "marca_dagua", "validade_orcamento_dias",
        ]

    def _codigo(self, campo, digitos):
        valor = "".join(filter(str.isdigit, self.cleaned_data.get(campo) or ""))
        if len(valor) != digitos:
            raise forms.ValidationError(f"Use {digitos} dígitos.")
        return valor

    def clean_cfop_venda(self):
        return self._codigo("cfop_venda", 4)

    def clean_cfop_venda_st(self):
        return self._codigo("cfop_venda_st", 4)

    def clean_cst_csosn_venda(self):
        valor = "".join(filter(str.isdigit, self.cleaned_data.get("cst_csosn_venda") or ""))
        if len(valor) not in (2, 3):
            raise forms.ValidationError("CSOSN tem 3 dígitos (Simples) e CST tem 2.")
        return valor

    def clean_cst_csosn_venda_st(self):
        valor = "".join(filter(str.isdigit, self.cleaned_data.get("cst_csosn_venda_st") or ""))
        if len(valor) not in (2, 3):
            raise forms.ValidationError("CSOSN tem 3 dígitos (Simples) e CST tem 2.")
        return valor

    def clean_cnpj(self):
        cnpj = self.cleaned_data["cnpj"].strip()
        if not cnpj:
            return ""
        if not cnpj_valido(cnpj):
            raise forms.ValidationError("CNPJ inválido — confira os números.")
        return formatar_cnpj(cnpj)

    def clean_uf(self):
        return self.cleaned_data["uf"].strip().upper()


class PerfilProfissionalForm(forms.ModelForm):
    """O que a própria pessoa edita em Meu perfil."""

    telefone = TelefoneField(label="Telefone de contato", required=False)

    class Meta:
        model = PerfilProfissional
        fields = [
            "nome_completo", "crmv", "crmv_uf", "mapa", "assinatura", "telefone",
            "cep", "endereco", "numero", "complemento", "bairro", "cidade", "uf",
        ]

    def clean_uf(self):
        return self.cleaned_data["uf"].strip().upper()

    def clean_crmv_uf(self):
        return self.cleaned_data["crmv_uf"].strip().upper()


class PerfilProfissionalAdminForm(PerfilProfissionalForm):
    """Admin da clínica (Usuários → Perfil) também define a data de admissão."""

    class Meta(PerfilProfissionalForm.Meta):
        fields = PerfilProfissionalForm.Meta.fields + ["data_admissao"]
        widgets = {"data_admissao": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


def _editar_perfil(request, usuario, voltar_para):
    perfil = PerfilProfissional.de(usuario)
    form_cls = PerfilProfissionalAdminForm if request.session.get("papel") == "admin" else PerfilProfissionalForm
    form = form_cls(request.POST or None, request.FILES or None, instance=perfil)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Perfil profissional salvo.")
        return redirect(voltar_para)
    return render(request, "core/perfil.html", {"form": form, "perfil": perfil, "pessoa": usuario, "voltar_para": voltar_para})


@login_required
def meu_perfil(request):
    return _editar_perfil(request, request.user, "core:meu_perfil")


@admin_required
def perfil_usuario(request, usuario_id):
    """Admin edita o perfil de alguém que tem acesso A ESTA clínica."""
    from apps.plataforma.models import UsuarioClinica

    vinculo = get_object_or_404(
        UsuarioClinica.objects.select_related("usuario"), usuario_id=usuario_id, clinica_id=request.session["clinica_id"],
    )
    return _editar_perfil(request, vinculo.usuario, "usuarios_clinica:lista")


@admin_required
def configuracao(request):
    config = ConfiguracaoClinica.atual()
    form = ConfiguracaoClinicaForm(request.POST or None, request.FILES or None, instance=config)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Dados da clínica salvos.")
        return redirect("core:configuracao")
    return render(request, "core/configuracao.html", {"form": form, "config": config})
