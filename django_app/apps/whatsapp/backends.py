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

    def enviar_modelo(self, conexao, numero: str, modelo, parametros, imagem_id: str = "") -> ResultadoEnvio:
        raise NotImplementedError

    def subir_imagem(self, conexao, conteudo: bytes, tipo: str, nome: str) -> str:
        """Id da imagem na Meta, pra ir no cabeçalho dos avisos."""
        raise NotImplementedError


class WhatsAppConsoleBackend(WhatsAppBackendBase):
    """Padrão em dev — não envia de verdade, só loga o texto que sairia."""

    def enviar_modelo(self, conexao, numero, modelo, parametros, imagem_id=""):
        logger.info("WHATSAPP (console, não enviado) para %s [%s]%s: %s", numero, modelo.nome,
                    f" com imagem {imagem_id}" if imagem_id else "", modelo.renderizar(parametros))
        return ResultadoEnvio(ok=True, wamid=f"console.{uuid.uuid4().hex}")

    def subir_imagem(self, conexao, conteudo, tipo, nome):
        return f"console-imagem.{uuid.uuid4().hex[:8]}"


class WhatsAppMetaCloudBackend(WhatsAppBackendBase):
    """Cloud API oficial, com o número e o token DA CLÍNICA (ConexaoWhatsApp)."""

    requer_conexao = True

    def enviar_modelo(self, conexao, numero, modelo, parametros, imagem_id=""):
        try:
            wamid = meta.enviar_modelo(conexao.phone_number_id, conexao.token, numero, modelo, parametros, imagem_id)
        except meta.ErroMeta as exc:
            logger.error("WhatsApp: erro da Meta ao enviar %s para %s: %s", modelo.nome, numero, exc)
            return ResultadoEnvio(ok=False, erro=str(exc))
        return ResultadoEnvio(ok=True, wamid=wamid)

    def subir_imagem(self, conexao, conteudo, tipo, nome):
        return meta.subir_midia(conexao.phone_number_id, conexao.token, conteudo, tipo, nome)


def get_backend() -> WhatsAppBackendBase:
    return import_string(settings.WHATSAPP_BACKEND)()
