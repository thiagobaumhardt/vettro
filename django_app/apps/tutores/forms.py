from django import forms

from apps.core.validators import cpf_valido

from .models import Tutor


class TutorForm(forms.ModelForm):
    consentimento_dados = forms.BooleanField(label="Consentimento LGPD", required=False)

    class Meta:
        model = Tutor
        fields = [
            "nome", "tel", "email", "cpf", "cep", "endereco", "numero", "complemento",
            "bairro", "cidade", "uf", "como_conheceu", "obs", "consentimento_dados",
        ]

    def clean_cpf(self):
        cpf = self.cleaned_data.get("cpf", "")
        if cpf and not cpf_valido(cpf):
            raise forms.ValidationError("CPF inválido.")
        return cpf
