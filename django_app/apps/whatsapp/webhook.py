"""Webhook da Meta — UMA URL pra todas as clínicas (configurada no app Meta do
Vettro): https://www.vettro.com.br/whatsapp/webhook/. Chega sem sessão
(URLconf público); a clínica é achada pelo phone_number_id (mensagens) ou
pelo waba_id (status de template) e o resto roda dentro do schema dela.

Trata:
- status das mensagens enviadas (entregue/lida/falhou) → MensagemWhatsApp;
- respostas dos tutores → MensagemWhatsApp tipo "resposta"; "SAIR" revoga o
  consentimento de WhatsApp do tutor (LGPD — opt-out pelo próprio canal);
- aprovação/recusa de template → ConexaoWhatsApp.modelos.

Sempre responde 200 depois de validar a assinatura — erro aqui faria a Meta
reenviar o mesmo evento por horas."""
import hashlib
import hmac
import json
import logging
import unicodedata

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django_tenants.utils import schema_context

from .models import ConexaoWhatsApp

logger = logging.getLogger("vettro.whatsapp")

PALAVRAS_SAIR = {"sair", "parar", "pare", "stop", "cancelar", "descadastrar"}

# Ordem do status — evento atrasado ("entregue" depois de "lida") não regride.
ORDEM_STATUS = {"enviada": 1, "entregue": 2, "lida": 3, "falhou": 4}
STATUS_META = {"sent": "enviada", "delivered": "entregue", "read": "lida", "failed": "falhou"}


@csrf_exempt
def webhook(request):
    if request.method == "GET":
        if (
            request.GET.get("hub.mode") == "subscribe"
            and settings.META_WEBHOOK_VERIFY_TOKEN
            and hmac.compare_digest(request.GET.get("hub.verify_token", ""), settings.META_WEBHOOK_VERIFY_TOKEN)
        ):
            return HttpResponse(request.GET.get("hub.challenge", ""))
        return HttpResponseForbidden()

    if request.method != "POST" or not _assinatura_valida(request):
        return HttpResponseForbidden()
    try:
        processar(json.loads(request.body))
    except Exception:  # noqa: BLE001 — loga e confirma, senão a Meta reenvia em loop
        logger.exception("WhatsApp: erro processando webhook")
    return HttpResponse("ok")


def _assinatura_valida(request) -> bool:
    segredo = settings.META_APP_SECRET
    if not segredo:
        return False
    esperado = "sha256=" + hmac.new(segredo.encode(), request.body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(request.headers.get("X-Hub-Signature-256", ""), esperado)


def processar(payload: dict):
    for entrada in payload.get("entry", []):
        for mudanca in entrada.get("changes", []):
            campo = mudanca.get("field")
            valor = mudanca.get("value") or {}
            if campo == "messages":
                _mensagens(valor)
            elif campo == "message_template_status_update":
                _status_modelo(entrada.get("id"), valor)


def _mensagens(valor: dict):
    phone_number_id = (valor.get("metadata") or {}).get("phone_number_id")
    conexao = ConexaoWhatsApp.objects.select_related("clinica").filter(phone_number_id=phone_number_id).first()
    if not conexao:
        return
    with schema_context(conexao.clinica.schema_name):
        for status in valor.get("statuses", []):
            _atualizar_status(status)
        for mensagem in valor.get("messages", []):
            _registrar_resposta(mensagem)


def _atualizar_status(status: dict):
    from apps.lembretes.models import MensagemWhatsApp

    novo = STATUS_META.get(status.get("status"))
    mensagem = MensagemWhatsApp.objects.filter(wamid=status.get("id", "-")).first()
    if not (novo and mensagem) or ORDEM_STATUS.get(novo, 0) <= ORDEM_STATUS.get(mensagem.status, 0):
        return
    mensagem.status = novo
    if novo == "falhou":
        erros = status.get("errors") or [{}]
        mensagem.erro = (erros[0].get("error_data") or {}).get("details") or erros[0].get("title", "Falha na entrega.")
    mensagem.save(update_fields=["status", "erro", "atualizado_em"])


def _texto_recebido(mensagem: dict) -> str:
    tipo = mensagem.get("type")
    if tipo == "text":
        return (mensagem.get("text") or {}).get("body", "")
    if tipo == "button":
        return (mensagem.get("button") or {}).get("text", "")
    if tipo == "interactive":
        interativo = mensagem.get("interactive") or {}
        resposta = interativo.get("button_reply") or interativo.get("list_reply") or {}
        return resposta.get("title", "")
    return f"[{tipo or 'mensagem'}]"


def _registrar_resposta(mensagem: dict):
    from apps.lembretes.models import MensagemWhatsApp
    from apps.tutores import services as tutores_services

    wamid = mensagem.get("id", "")
    if not wamid or MensagemWhatsApp.objects.filter(wamid=wamid).exists():
        return  # a Meta reenvia o mesmo evento
    telefone = mensagem.get("from", "")
    texto = _texto_recebido(mensagem)
    tutor = encontrar_tutor(telefone)

    descadastrou = False
    if tutor and tutor.consentimento_whatsapp and _normalizar(texto) in PALAVRAS_SAIR:
        tutores_services.salvar_consentimento_whatsapp(tutor, True, False)
        tutor.save(update_fields=["consentimento_whatsapp", "consentimento_whatsapp_em"])
        descadastrou = True

    MensagemWhatsApp.objects.create(
        tipo=MensagemWhatsApp.Tipo.RESPOSTA, tutor=tutor, telefone=f"+{telefone}", texto=texto[:4000],
        wamid=wamid, status=MensagemWhatsApp.Status.RECEBIDA, descadastrou=descadastrou,
    )


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return sem_acento.strip().strip(".!").lower()


def encontrar_tutor(wa_id: str):
    from apps.tutores.models import Tutor

    from .services import chave_telefone

    chave = chave_telefone(f"+{wa_id}")
    if len(chave) < 4:
        return None
    for tutor in Tutor.objects.filter(tel__endswith=chave[-4:]):
        if chave_telefone(tutor.tel) == chave:
            return tutor
    return None


def _status_modelo(waba_id: str, valor: dict):
    nome = valor.get("message_template_name")
    if not nome:
        return
    for conexao in ConexaoWhatsApp.objects.filter(waba_id=waba_id):
        if nome not in conexao.modelos:
            continue
        situacao = conexao.modelos[nome]
        situacao["status"] = valor.get("event", situacao.get("status", ""))
        motivo = valor.get("reason")
        situacao["motivo"] = "" if motivo in (None, "NONE") else motivo
        conexao.save(update_fields=["modelos", "atualizado_em"])
