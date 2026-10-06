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


def cnpj_valido(cnpj: str) -> bool:
    """Dígitos verificadores do CNPJ (mod 11, pesos 5..2/9..2 e 6..2/9..2)."""
    digitos = re.sub(r"\D", "", cnpj or "")
    if len(digitos) != 14 or digitos == digitos[0] * 14:
        return False

    def _dv(base: str) -> int:
        pesos = list(range(len(base) - 7, 1, -1)) + list(range(9, 1, -1))
        resto = sum(int(d) * p for d, p in zip(base, pesos)) % 11
        return 0 if resto < 2 else 11 - resto

    return digitos[-2:] == f"{_dv(digitos[:12])}{_dv(digitos[:13])}"


def formatar_cnpj(cnpj: str) -> str:
    d = re.sub(r"\D", "", cnpj or "")
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else cnpj


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


def formatar_telefone(valor: str) -> str:
    """Normaliza telefone para "+55 (51) 9 9999-9999" (celular) ou "+55 (51) 3333-4444"
    (fixo). Sem DDI assume Brasil (55). Outro DDI ("+1 202...") fica "+<ddi> <dígitos>".
    Vazio continua vazio. ValidationError se o número brasileiro estiver incompleto
    ou se o celular (11 dígitos) não tiver o 9 depois do DDD."""
    valor = (valor or "").strip()
    digitos = re.sub(r"\D", "", valor)
    if not digitos:
        return ""
    com_ddi = re.match(r"^\+(\d{1,3})(?=\D|$)", valor)
    if com_ddi:
        ddi, resto = com_ddi.group(1), re.sub(r"\D", "", valor[com_ddi.end():])
    elif len(digitos) in (12, 13) and digitos.startswith("55"):
        ddi, resto = "55", digitos[2:]
    else:
        ddi, resto = "55", digitos

    if ddi != "55":
        if not 6 <= len(resto) <= 14:
            raise ValidationError("Telefone internacional inválido.")
        return f"+{ddi} {resto}"
    if len(resto) == 11:
        if resto[2] != "9":
            raise ValidationError("Celular deve ter o 9 logo depois do DDD (ex.: +55 (51) 9 9999-9999).")
        return f"+55 ({resto[:2]}) {resto[2]} {resto[3:7]}-{resto[7:]}"
    if len(resto) == 10:
        return f"+55 ({resto[:2]}) {resto[2:6]}-{resto[6:]}"
    raise ValidationError("Telefone incompleto: informe DDD + número (ex.: +55 (51) 9 9999-9999).")
