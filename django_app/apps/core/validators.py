import re


def cpf_valido(cpf: str) -> bool:
    """Porte direto do algoritmo mod-11 de validação de CPF
    (backend/app/utils.py do sistema FastAPI atual)."""
    digitos = re.sub(r"\D", "", cpf or "")
    if len(digitos) != 11 or digitos == digitos[0] * 11:
        return False

    def _dv(base: str) -> int:
        soma = sum(int(d) * peso for d, peso in zip(base, range(len(base) + 1, 1, -1)))
        resto = (soma * 10) % 11
        return 0 if resto == 10 else resto

    return digitos[-2:] == f"{_dv(digitos[:9])}{_dv(digitos[:10])}"


from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible


@deconstructible
class TamanhoArquivoValidator:
    """Validator pra FileField/ImageField — porte do validar_tamanho_base64
    do FastAPI, agora operando sobre file.size direto (não precisa mais da
    matemática de aproximação de base64). Classe (não closure) pra ser
    serializável em migrations."""

    def __init__(self, max_bytes: int, campo: str = "arquivo"):
        self.max_bytes = max_bytes
        self.campo = campo

    def __call__(self, arquivo):
        if arquivo.size > self.max_bytes:
            max_mb = self.max_bytes / (1024 * 1024)
            raise ValidationError(f"{self.campo} excede o limite de {max_mb:.0f}MB.")

    def __eq__(self, other):
        return (
            isinstance(other, TamanhoArquivoValidator)
            and self.max_bytes == other.max_bytes
            and self.campo == other.campo
        )
