from django import forms

from apps.core.campos import TelefoneField
from apps.core.validators import cpf_valido

from .models import Tutor


class TutorForm(forms.ModelForm):
    tel = TelefoneField(label="WhatsApp")
    tel2 = TelefoneField(label="Outro telefone", required=False)
    consentimento_dados = forms.BooleanField(label="Consentimento LGPD", required=False)
    consentimento_whatsapp = forms.BooleanField(label="Consentimento p/ lembrete de WhatsApp", required=False)

    class Meta:
        model = Tutor
        fields = [
            "nome", "tel", "tel2", "email", "cpf", "rg", "cep", "endereco", "numero", "complemento",
            "bairro", "cidade", "uf", "como_conheceu", "obs",
            "consentimento_dados", "consentimento_whatsapp",
        ]

    def clean_cpf(self):
        cpf = self.cleaned_data.get("cpf", "")
        if cpf and not cpf_valido(cpf):
            raise forms.ValidationError("CPF inválido.")
        return cpf
