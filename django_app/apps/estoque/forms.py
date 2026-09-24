from django import forms

from .models import Insumo


class InsumoForm(forms.ModelForm):
    class Meta:
        model = Insumo
        fields = [
            "nome", "categoria", "valor", "codigo_barras", "unidades_por_pacote",
            "data_validade", "lote", "ncm", "cfop", "cst_csosn", "tipo_fiscal", "obs",
        ]
        widgets = {"data_validade": forms.DateInput(attrs={"type": "date"})}

    def clean_codigo_barras(self):
        codigo = self.cleaned_data.get("codigo_barras") or None
        if codigo:
            existe = Insumo.objects.filter(codigo_barras=codigo).exclude(pk=self.instance.pk)
            if existe.exists():
                raise forms.ValidationError("Já existe um insumo com esse código de barras.")
        return codigo


class EntradaManualForm(forms.Form):
    insumo = forms.ModelChoiceField(queryset=Insumo.objects.all())
    quantidade = forms.IntegerField(min_value=1)
    valor_unitario = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    lote = forms.CharField(max_length=60, required=False)
    data_validade = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    observacao = forms.CharField(max_length=300, required=False)


class AjusteForm(forms.Form):
    quantidade = forms.IntegerField(min_value=1)
    sinal = forms.ChoiceField(choices=[("positivo", "Entrada (+)"), ("negativo", "Saída (-)")])
    motivo = forms.CharField(max_length=300)
