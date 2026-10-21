"""Camada de envio trocável (mesmo princípio do TEF e da nota fiscal):
WHATSAPP_BACKEND escolhe entre o console (dev — só loga) e a Cloud API da
Meta (oficial). Alternativas tipo Z-API/Evolution API conectam via QR Code,
simulam o WhatsApp Web e correm risco real de banimento do número — só a API
oficial é livre desse risco."""
import logging
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.utils.module_loading import import_string

from . import meta

logger = logging.getLogger("vettro.whatsapp")


@dataclass
class ResultadoEnvio:
    ok: bool
    wamid: str = ""
    erro: str = ""


class WhatsAppBackendBase:
    # True = só envia com a clínica conectada (ConexaoWhatsApp ativa e template aprovado).
    requer_conexao = False

    def enviar_modelo(self, conexao, numero: str, modelo, parametros) -> ResultadoEnvio:
        raise NotImplementedError


class WhatsAppConsoleBackend(WhatsAppBackendBase):
    """Padrão em dev — não envia de verdade, só loga o texto que sairia."""

    def enviar_modelo(self, conexao, numero, modelo, parametros):
        logger.info("WHATSAPP (console, não enviado) para %s [%s]: %s", numero, modelo.nome, modelo.renderizar(parametros))
        return ResultadoEnvio(ok=True, wamid=f"console.{uuid.uuid4().hex}")


class WhatsAppMetaCloudBackend(WhatsAppBackendBase):
    """Cloud API oficial, com o número e o token DA CLÍNICA (ConexaoWhatsApp)."""

    requer_conexao = True

    def enviar_modelo(self, conexao, numero, modelo, parametros):
        try:
            wamid = meta.enviar_modelo(conexao.phone_number_id, conexao.token, numero, modelo, parametros)
        except meta.ErroMeta as exc:
            logger.error("WhatsApp: erro da Meta ao enviar %s para %s: %s", modelo.nome, numero, exc)
            return ResultadoEnvio(ok=False, erro=str(exc))
        return ResultadoEnvio(ok=True, wamid=wamid)


def get_backend() -> WhatsAppBackendBase:
    return import_string(settings.WHATSAPP_BACKEND)()
