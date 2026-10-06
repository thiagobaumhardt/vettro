"""{% static_v 'dist/styles.css' %} — igual ao {% static %}, mas com ?v=<mtime>
no final: o navegador baixa de novo sempre que o arquivo muda (sem isso o CSS
antigo fica preso no cache e as mudanças de visual "não aparecem")."""
from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def static_v(caminho: str) -> str:
    url = static(caminho)
    arquivo = finders.find(caminho)
    if not arquivo:
        return url
    from os.path import getmtime

    return f"{url}?v={int(getmtime(arquivo))}"
