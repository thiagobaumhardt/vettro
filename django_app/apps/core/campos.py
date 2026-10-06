"""Campos de formulário reutilizados entre apps."""
from django import forms

from .validators import formatar_telefone


class TelefoneField(forms.CharField):
    """Telefone com DDI: "+55 (51) 9 9999-9999" (celular) ou "+55 (51) 3333-4444"
    (fixo). Sem DDI assume Brasil; outro DDI ("+1 ...") é aceito e guardado só
    com os dígitos. A máscara no navegador vem de static/js/mascaras.js
    (data-mascara="telefone"); a validação/normalização de verdade é aqui."""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", 20)
        kwargs.setdefault("widget", forms.TextInput(attrs={
            "data-mascara": "telefone", "inputmode": "tel", "autocomplete": "tel",
            "placeholder": "+55 (51) 9 9999-9999",
        }))
        super().__init__(**kwargs)

    def clean(self, value):
        return formatar_telefone(super().clean(value))
