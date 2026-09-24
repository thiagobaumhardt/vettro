import re

from django.core.exceptions import ValidationError


class LetrasEDigitosValidator:
    """Replica a política de senha do sistema FastAPI atual: mínimo 8
    caracteres (via MinimumLengthValidator) e mistura de letras e números."""

    def validate(self, password, user=None):
        if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
            raise ValidationError(
                "A senha precisa conter letras e números.",
                code="password_sem_letras_ou_digitos",
            )

    def get_help_text(self):
        return "Sua senha precisa conter letras e números."
