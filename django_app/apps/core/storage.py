import os

from django.core.files.storage import FileSystemStorage
from django.db import connection


class TenantFileSystemStorage(FileSystemStorage):
    """Isola uploads por clínica: cada schema de tenant grava fisicamente em
    media/<schema_name>/..., mas o nome guardado no campo do model continua
    relativo (sem o prefixo) — o prefixo é resolvido em tempo real a partir
    do schema ativo na conexão (TenantFromSessionMiddleware já garante isso
    antes de qualquer view rodar). Ver §3 do plano: evita que o upload de uma
    clínica apareça no namespace de outra."""

    def _caminho_tenant(self, name):
        schema = getattr(connection, "schema_name", "public")
        return os.path.join(schema, name)

    def path(self, name):
        return super().path(self._caminho_tenant(name))

    # `path` põe o prefixo, e o FileSystemStorage usa self.path() pra gravar,
    # abrir, checar, medir e apagar — por isso exists/delete/size não são
    # sobrescritos (prefixavam duas vezes: media/<schema>/<schema>/...).

    def _save(self, name, content):
        # O super devolve o caminho relativo ao MEDIA_ROOT, já com o schema e
        # sempre com "/" (inclusive no Windows) — o campo guarda sem o schema.
        salvo = super()._save(name, content)
        prefixo = getattr(connection, "schema_name", "public") + "/"
        return salvo[len(prefixo):] if salvo.startswith(prefixo) else salvo

    def url(self, name):
        return super().url(self._caminho_tenant(name))
