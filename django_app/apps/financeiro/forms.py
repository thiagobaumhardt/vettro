from django import forms

from .models import CirurgiaCategoria, Servico


class ServicoForm(forms.ModelForm):
    class Meta:
        model = Servico
        fields = ["nome", "valor", "descricao", "codigo_servico_municipal"]


class CirurgiaCategoriaForm(forms.ModelForm):
    class Meta:
        model = CirurgiaCategoria
        fields = ["nome", "valor_p", "valor_m", "valor_g", "descricao"]

    def clean(self):
        dados = super().clean()
        if not any([dados.get("valor_p"), dados.get("valor_m"), dados.get("valor_g")]):
            raise forms.ValidationError("Informe ao menos um valor de faixa de peso (P, M ou G).")
        return dados
