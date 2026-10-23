from django import template

register = template.Library()


def texto_duracao(minutos) -> str:
    """120 -> "2h", 90 -> "1h 30m", 45 -> "45 min"."""
    try:
        minutos = int(minutos)
    except (TypeError, ValueError):
        return ""
    h, m = divmod(minutos, 60)
    if not h:
        return f"{m} min"
    return f"{h}h" + (f" {m}m" if m else "")


@register.filter
def duracao(minutos) -> str:
    return texto_duracao(minutos)


@register.filter
def moeda(valor) -> str:
    """1234.5 -> "R$ 1.234,50"."""
    from decimal import Decimal, InvalidOperation

    try:
        valor = Decimal(str(valor or 0)).quantize(Decimal("0.01"))
    except InvalidOperation:
        return ""
    texto = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'- ' if valor < 0 else ''}R$ {texto}"
