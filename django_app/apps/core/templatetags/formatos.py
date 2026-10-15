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
