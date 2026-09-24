"""Camada de envio de WhatsApp — interface substituível, igual ao princípio
usado pra maquininha/TEF (§8 do plano). O provedor (Z-API, Meta Cloud API,
Twilio...) ainda não foi escolhido pelo usuário; enquanto isso, o backend
padrão só loga a mensagem, permitindo desenvolver e testar todo o resto do
fluxo (comando de lembrete, marcação de enviado) sem depender da escolha."""
import logging

from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger("vettro.whatsapp")


class WhatsAppBackendBase:
    def enviar(self, telefone: str, mensagem: str) -> bool:
        raise NotImplementedError


class WhatsAppConsoleBackend(WhatsAppBackendBase):
    """Backend padrão/placeholder — não envia de verdade, só loga. Trocar
    por um backend real assim que o provedor for escolhido: nenhum outro
    código (o comando de lembrete, os models) precisa mudar, só a setting
    WHATSAPP_BACKEND."""

    def enviar(self, telefone: str, mensagem: str) -> bool:
        logger.info("WHATSAPP (console, não enviado de verdade) para %s: %s", telefone, mensagem)
        return True


def get_backend() -> WhatsAppBackendBase:
    caminho = getattr(settings, "WHATSAPP_BACKEND", "apps.agenda.notificacoes.WhatsAppConsoleBackend")
    return import_string(caminho)()


def montar_mensagem_lembrete(agendamento) -> str:
    nome_tutor = agendamento.tutor_nome or "tutor(a)"
    if agendamento.hora:
        return (
            f"Olá, {nome_tutor}! Passando pra lembrar do agendamento de {agendamento.pac_nome} "
            f"amanhã ({agendamento.data:%d/%m}) às {agendamento.hora:%H:%M}."
        )
    return f"Olá, {nome_tutor}! Passando pra lembrar do agendamento de {agendamento.pac_nome} amanhã ({agendamento.data:%d/%m})."
