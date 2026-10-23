from django import template

from apps.estoque import services

register = template.Library()


@register.simple_tag
def total_avisos_estoque() -> int:
    """Número de avisos pro rótulo da aba "Avisos" do Estoque."""
    return services.resumo_avisos()["total"]
