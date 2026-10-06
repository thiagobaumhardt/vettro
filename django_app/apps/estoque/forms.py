from decimal import Decimal

from django import forms

from .models import Insumo


class InsumoForm(forms.ModelForm):
    class Meta:
        model = Insumo
        fields = [
            "nome", "categoria", "unidade", "embalagem", "unidades_por_pacote", "valor", "estoque_minimo",
            "codigo_barras", "data_validade", "lote", "ncm", "origem", "tem_st", "cfop", "cst_csosn", "tipo_fiscal", "obs",
        ]
        widgets = {
            "data_validade": forms.DateInput(attrs={"type": "date"}),
            "unidade": forms.Select(attrs={"x-model": "unidade"}),
            "embalagem": forms.TextInput(attrs={"x-model": "embalagem"}),
            "unidades_por_pacote": forms.NumberInput(attrs={"step": "any", "x-model": "conteudo"}),
            "valor": forms.NumberInput(attrs={"step": "0.01", "x-model": "valor"}),
            "estoque_minimo": forms.NumberInput(attrs={"step": "any"}),
        }

    def clean_ncm(self):
        ncm = "".join(filter(str.isdigit, self.cleaned_data.get("ncm") or ""))
        if ncm and len(ncm) != 8:
            raise forms.ValidationError("O NCM tem 8 dígitos (ex.: 3004.90.99 → 30049099).")
        return ncm

    def clean_codigo_barras(self):
        codigo = self.cleaned_data.get("codigo_barras") or None
        if codigo:
            existe = Insumo.objects.filter(codigo_barras=codigo).exclude(pk=self.instance.pk)
            if existe.exists():
                raise forms.ValidationError("Já existe um insumo com esse código de barras.")
        return codigo


class EntradaManualForm(forms.Form):
    LANCAR_EM_CHOICES = [("embalagem", "Embalagens"), ("unidade", "Unidades de uso")]

    insumo = forms.ModelChoiceField(queryset=Insumo.objects.all(), widget=forms.Select(attrs={"x-model": "insumoId"}))
    quantidade = forms.DecimalField(
        min_value=Decimal("0.001"), max_digits=12, decimal_places=3,
        widget=forms.NumberInput(attrs={"step": "any", "x-model": "quantidade"}),
    )
    lancar_em = forms.ChoiceField(
        choices=LANCAR_EM_CHOICES, initial="embalagem", widget=forms.Select(attrs={"x-model": "lancarEm"}),
    )
    valor_unitario = forms.DecimalField(
        max_digits=12, decimal_places=4, required=False, min_value=0,
        widget=forms.NumberInput(attrs={"step": "any"}),
        help_text="Custo de cada item lançado (por embalagem ou por unidade, conforme acima).",
    )
    lote = forms.CharField(max_length=60, required=False)
    data_validade = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    observacao = forms.CharField(max_length=300, required=False)


class AjusteForm(forms.Form):
    quantidade = forms.DecimalField(min_value=Decimal("0.001"), max_digits=12, decimal_places=3)  # unidade de uso
    sinal = forms.ChoiceField(choices=[("positivo", "Entrada (+)"), ("negativo", "Saída (-)")])
    motivo = forms.CharField(max_length=300)
