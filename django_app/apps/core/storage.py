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

    def exists(self, name):
        return super().exists(self._caminho_tenant(name))

    def _save(self, name, content):
        nome_completo = self._caminho_tenant(name)
        salvo = super()._save(nome_completo, content)
        schema = getattr(connection, "schema_name", "public")
        prefixo = schema + os.sep
        return salvo[len(prefixo):] if salvo.startswith(prefixo) else salvo

    def url(self, name):
        return super().url(self._caminho_tenant(name))

    def delete(self, name):
        return super().delete(self._caminho_tenant(name))

    def size(self, name):
        return super().size(self._caminho_tenant(name))
