from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .campos import TelefoneField
from .decorators import admin_required
from .models import ConfiguracaoClinica, DocumentoEmpresa, PerfilProfissional
from .validators import cnpj_valido, formatar_cnpj


def health(request):
    return JsonResponse({"status": "ok"})


class ConfiguracaoClinicaForm(forms.ModelForm):
    telefone = TelefoneField(required=False)
    # Certificado A1: o arquivo e a senha não ficam no formulário — vão cifrados
    # pro banco em `save` (ConfiguracaoClinica.guardar_certificado).
    certificado = forms.FileField(label="Certificado digital A1 (.pfx)", required=False)
    certificado_senha = forms.CharField(label="Senha do certificado", required=False,
                                        widget=forms.PasswordInput(render_value=False))
    remover_certificado = forms.BooleanField(label="Remover certificado", required=False)

    class Meta:
        model = ConfiguracaoClinica
        fields = [
            "razao_social", "cnpj", "inscricao_estadual", "telefone", "email",
            "cep", "endereco", "numero", "complemento", "bairro", "cidade", "uf",
            "regime_tributario", "cfop_venda", "cst_csosn_venda", "cfop_venda_st", "cst_csosn_venda_st",
            "nfse_codigo_tributacao_nacional", "nfse_codigo_municipal", "tef_terminal_token",
            "codigo_municipio_ibge", "inscricao_municipal", "nfse_ambiente", "nfse_serie", "nfse_aliquota_simples",
            "marca_dagua", "validade_orcamento_dias", "agenda_hora_inicio", "agenda_hora_fim", "agenda_intervalo_min",
        ]

    def _codigo(self, campo, digitos):
        valor = "".join(filter(str.isdigit, self.cleaned_data.get(campo) or ""))
        if len(valor) != digitos:
            raise forms.ValidationError(f"Use {digitos} dígitos.")
        return valor

    def clean_nfse_codigo_tributacao_nacional(self):
        return self._codigo("nfse_codigo_tributacao_nacional", 6)

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

    def clean_inscricao_estadual(self):
        valor = (self.cleaned_data.get("inscricao_estadual") or "").strip().upper()
        if valor and valor not in ("ISENTO",) and not 2 <= len("".join(filter(str.isdigit, valor))) <= 14:
            raise forms.ValidationError("Inscrição estadual inválida — use os números do cadastro da Receita Estadual (ou ISENTO).")
        return valor

    def clean_tef_terminal_token(self):
        return "".join((self.cleaned_data.get("tef_terminal_token") or "").split()).upper()

    def clean_codigo_municipio_ibge(self):
        valor = "".join(filter(str.isdigit, self.cleaned_data.get("codigo_municipio_ibge") or ""))
        if valor and len(valor) != 7:
            raise forms.ValidationError("O código IBGE do município tem 7 dígitos.")
        return valor

    def clean_nfse_codigo_municipal(self):
        return (self.cleaned_data.get("nfse_codigo_municipal") or "").strip()

    def clean_nfse_serie(self):
        valor = "".join(filter(str.isdigit, self.cleaned_data.get("nfse_serie") or ""))
        # 1–49999 = sistema próprio; 70000–79999 é a faixa do portal gov.br (emissão manual).
        if not valor or not 1 <= int(valor) <= 49999:
            raise forms.ValidationError("Série da DPS de sistema próprio: de 1 a 49999 (70000–79999 é do portal gov.br).")
        return str(int(valor))

    def clean(self):
        dados = super().clean()
        arquivo = dados.get("certificado")
        self._certificado = None
        if arquivo:
            from apps.pagamentos.nfse_nacional import ler_certificado
            from apps.pagamentos.notas import NotaFiscalError

            pfx = arquivo.read()
            try:
                cert = ler_certificado(pfx, dados.get("certificado_senha") or "")
            except NotaFiscalError as exc:
                self.add_error("certificado", str(exc))
                return dados
            cnpj = "".join(filter(str.isdigit, dados.get("cnpj") or ""))
            if cert.cnpj and cnpj and cert.cnpj != cnpj:
                self.add_error("certificado", "Este certificado é de outro CNPJ — use o e-CNPJ da clínica.")
            self._certificado = (pfx, dados.get("certificado_senha") or "", cert)
        return dados

    def save(self, commit=True):
        config = super().save(commit=False)
        if self._certificado:
            pfx, senha, cert = self._certificado
            config.guardar_certificado(pfx, senha, titular=cert.titular, validade=cert.validade)
        elif self.cleaned_data.get("remover_certificado"):
            config.guardar_certificado(b"", "", titular="", validade=None)
        if commit:
            config.save()
            self.save_m2m()
        return config


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


# Abas da tela Clínica: campo → aba (abre na aba do primeiro erro).
ABAS_CONFIGURACAO = {
    "identificacao": ["razao_social", "cnpj", "inscricao_estadual", "inscricao_municipal", "telefone", "email"],
    "endereco": ["cep", "endereco", "numero", "complemento", "bairro", "cidade", "uf", "codigo_municipio_ibge"],
    "fiscal": ["regime_tributario", "cfop_venda", "cst_csosn_venda", "cfop_venda_st", "cst_csosn_venda_st",
               "nfse_codigo_tributacao_nacional", "nfse_codigo_municipal", "nfse_aliquota_simples"],
    "certificado": ["nfse_ambiente", "nfse_serie", "certificado", "certificado_senha", "remover_certificado"],
    "maquininha": ["tef_terminal_token"],
    "agenda": ["agenda_hora_inicio", "agenda_hora_fim", "agenda_intervalo_min"],
    "documentos": ["validade_orcamento_dias", "marca_dagua"],
    "empresa": [],
    "whatsapp": [],
}


def _aba_inicial(request, form) -> str:
    for aba, campos in ABAS_CONFIGURACAO.items():
        if any(c in form.errors for c in campos):
            return aba
    pedida = request.POST.get("aba") or request.GET.get("aba")
    return pedida if pedida in ABAS_CONFIGURACAO else "identificacao"


@admin_required
def configuracao(request):
    config = ConfiguracaoClinica.atual()
    form = ConfiguracaoClinicaForm(request.POST or None, request.FILES or None, instance=config)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Dados da clínica salvos.")
        if "tef_terminal_token" in form.changed_data and config.tef_terminal_token:
            from apps.pagamentos.services import TEFError, vincular_terminal

            try:
                vincular_terminal(config.tef_terminal_token)
                messages.success(request, "Maquininha vinculada ao Vettro.")
            except TEFError as exc:
                messages.error(request, f"Não foi possível vincular a maquininha: {exc}")
        return redirect(f"{reverse('core:configuracao')}?aba={_aba_inicial(request, form)}")
    return render(request, "core/configuracao.html", {
        "form": form, "config": config, "aba_inicial": _aba_inicial(request, form),
        "documentos_empresa": DocumentoEmpresa.objects.all(), "tipos_documento": DocumentoEmpresa.TIPO_CHOICES,
    })


class DocumentoEmpresaForm(forms.ModelForm):
    class Meta:
        model = DocumentoEmpresa
        fields = ["tipo", "descricao", "arquivo"]


def _voltar_documentos():
    return redirect(f"{reverse('core:configuracao')}?aba=empresa")


@admin_required
def documento_empresa_enviar(request):
    if request.method == "POST":
        form = DocumentoEmpresaForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.nome_arquivo = request.FILES["arquivo"].name[:200]
            doc.enviado_por_nome = getattr(request.user, "nome", "")
            doc.save()
            messages.success(request, f"{doc.get_tipo_display()} anexado.")
        else:
            messages.error(request, " ".join(e for erros in form.errors.values() for e in erros))
    return _voltar_documentos()


@admin_required
def documento_empresa(request, pk):
    """Abre o arquivo pra quem é admin — os documentos não têm link público."""
    doc = get_object_or_404(DocumentoEmpresa, pk=pk)
    try:
        arquivo = doc.arquivo.open("rb")
    except OSError:
        raise Http404("Arquivo não encontrado.")
    return FileResponse(arquivo, filename=doc.nome_arquivo, as_attachment=False)


@admin_required
def documento_empresa_excluir(request, pk):
    doc = get_object_or_404(DocumentoEmpresa, pk=pk)
    if request.method == "POST":
        doc.arquivo.delete(save=False)
        doc.delete()
        messages.success(request, "Documento excluído.")
    return _voltar_documentos()
