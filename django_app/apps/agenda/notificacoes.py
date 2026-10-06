"""Camada de envio de WhatsApp — interface substituível, igual ao princípio
usado pra maquininha/TEF (§8 do plano). Provedor escolhido: **Meta Cloud API
oficial** — decisão tomada depois de pesquisa mostrando que alternativas tipo
Z-API/Evolution API conectam via QR Code (simulam o WhatsApp Web) e correm
risco real de banimento do número em 2026 (Meta intensificou o bloqueio
dessas ferramentas), independente de serem pagas ou não. Só a API oficial
(WABA via Meta Business Manager) é livre desse risco."""
import logging
import re

import requests
from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger("vettro.whatsapp")


class WhatsAppBackendBase:
    def enviar(self, telefone: str, mensagem: str) -> bool:
        raise NotImplementedError


class WhatsAppConsoleBackend(WhatsAppBackendBase):
    """Backend padrão/placeholder — não envia de verdade, só loga. Continua
    sendo o default enquanto a clínica não configurar as credenciais reais
    da Meta (§ abaixo) — nenhum outro código (comando de lembrete, models)
    precisa mudar pra trocar, só a setting WHATSAPP_BACKEND."""

    def enviar(self, telefone: str, mensagem: str) -> bool:
        logger.info("WHATSAPP (console, não enviado de verdade) para %s: %s", telefone, mensagem)
        return True


def _normalizar_telefone(telefone: str) -> str | None:
    """Meta exige o número em formato E.164 sem o "+" (ex: 5551999998888).
    Assume Brasil (DDI 55) quando o número informado só tem DDD+número."""
    digitos = re.sub(r"\D", "", telefone or "")
    if not digitos:
        return None
    if (telefone or "").strip().startswith("+"):
        return digitos  # já veio com DDI ("+55 (51) 9 ...", "+1 202 ...")
    if digitos.startswith("55") and len(digitos) in (12, 13):
        return digitos
    if len(digitos) in (10, 11):  # DDD + número, sem o DDI
        return f"55{digitos}"
    return digitos


class WhatsAppMetaCloudBackend(WhatsAppBackendBase):
    """Backend real via WhatsApp Cloud API da Meta (oficial, Graph API).

    Mensagem de negócio-pra-cliente fora de uma janela de atendimento de 24h
    (que é exatamente o caso do lembrete — a clínica inicia a conversa, o
    tutor não escreveu primeiro) **só pode ser enviada via template
    pré-aprovado** pela Meta — texto livre é rejeitado pela API nesse
    cenário. Por isso o texto já montado por `montar_mensagem_lembrete` vira
    a variável {{1}} de um template genérico de 1 variável (ex: corpo
    "Olá! {{1}}"), em vez de mandar texto livre.

    Configuração necessária (settings/env, todas vazias por padrão — sem
    elas o backend loga erro e não envia, não quebra o resto do fluxo):
    - WHATSAPP_META_TOKEN: token de acesso (system user, de longa duração)
    - WHATSAPP_META_PHONE_NUMBER_ID: ID do número cadastrado na WABA
    - WHATSAPP_META_TEMPLATE_NAME: nome do template aprovado (categoria utility)
    - WHATSAPP_META_TEMPLATE_LANG: idioma do template (padrão "pt_BR")
    """

    API_VERSION = "v21.0"

    def enviar(self, telefone: str, mensagem: str) -> bool:
        token = getattr(settings, "WHATSAPP_META_TOKEN", "")
        phone_number_id = getattr(settings, "WHATSAPP_META_PHONE_NUMBER_ID", "")
        template_name = getattr(settings, "WHATSAPP_META_TEMPLATE_NAME", "")
        template_lang = getattr(settings, "WHATSAPP_META_TEMPLATE_LANG", "pt_BR")

        if not (token and phone_number_id and template_name):
            logger.error(
                "WhatsAppMetaCloudBackend: configuração incompleta (WHATSAPP_META_TOKEN/"
                "PHONE_NUMBER_ID/TEMPLATE_NAME) — mensagem NÃO enviada para %s.", telefone,
            )
            return False

        numero = _normalizar_telefone(telefone)
        if not numero:
            logger.error("WhatsAppMetaCloudBackend: telefone inválido, mensagem não enviada: %r", telefone)
            return False

        payload = {
            "messaging_product": "whatsapp",
            "to": numero,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": template_lang},
                "components": [
                    {"type": "body", "parameters": [{"type": "text", "text": mensagem}]},
                ],
            },
        }

        try:
            resposta = requests.post(
                f"https://graph.facebook.com/{self.API_VERSION}/{phone_number_id}/messages",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
        except requests.RequestException:
            logger.exception("WhatsAppMetaCloudBackend: falha de rede ao enviar para %s.", numero)
            return False

        if resposta.status_code >= 400:
            logger.error(
                "WhatsAppMetaCloudBackend: erro %s da Meta ao enviar para %s: %s",
                resposta.status_code, numero, resposta.text,
            )
            return False

        message_id = (resposta.json().get("messages") or [{}])[0].get("id")
        logger.info("WhatsAppMetaCloudBackend: enviado para %s (message_id=%s).", numero, message_id)
        return True


def get_backend() -> WhatsAppBackendBase:
    caminho = getattr(settings, "WHATSAPP_BACKEND", "apps.agenda.notificacoes.WhatsAppConsoleBackend")
    return import_string(caminho)()


def montar_mensagem_proxima_dose(atendimento, clinica_nome: str) -> str:
    nome_tutor = (atendimento.paciente.tutor.nome.split(" ")[0] if atendimento.paciente and atendimento.paciente.tutor else "") or "tutor(a)"
    return (
        f"Olá, {nome_tutor}! Aqui é da {clinica_nome}. Passando pra lembrar que a próxima dose da vacina "
        f"{atendimento.vacina_nome} de {atendimento.pac_nome} está marcada para {atendimento.data_proxima_dose:%d/%m/%Y}. "
        f"Responda esta mensagem para agendar."
    )


def montar_mensagem_retorno(atendimento, clinica_nome: str) -> str:
    nome_tutor = (atendimento.paciente.tutor.nome.split(" ")[0] if atendimento.paciente and atendimento.paciente.tutor else "") or "tutor(a)"
    return (
        f"Olá, {nome_tutor}! Aqui é da {clinica_nome}. Passando pra lembrar que o retorno de "
        f"{atendimento.pac_nome} está previsto para {atendimento.data_retorno:%d/%m/%Y}. "
        f"Responda esta mensagem para agendar."
    )


def montar_mensagem_lembrete(agendamento) -> str:
    nome_tutor = agendamento.tutor_nome or "tutor(a)"
    if agendamento.hora:
        return (
            f"Olá, {nome_tutor}! Passando pra lembrar do agendamento de {agendamento.pac_nome} "
            f"amanhã ({agendamento.data:%d/%m}) às {agendamento.hora:%H:%M}."
        )
    return f"Olá, {nome_tutor}! Passando pra lembrar do agendamento de {agendamento.pac_nome} amanhã ({agendamento.data:%d/%m})."
