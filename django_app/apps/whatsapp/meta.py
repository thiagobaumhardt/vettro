"""Cliente fino da Graph API (WhatsApp Cloud API) — só as chamadas que o
Vettro usa. Toda falha vira ErroMeta com a mensagem da Meta (em geral já
legível pro usuário: "error_user_msg")."""
import requests
from django.conf import settings

from .modelos import IDIOMA


class ErroWhatsApp(Exception):
    pass


class ErroMeta(ErroWhatsApp):
    def __init__(self, mensagem, codigo=None):
        super().__init__(mensagem)
        self.codigo = codigo


def _url(caminho: str) -> str:
    return f"https://graph.facebook.com/{settings.META_GRAPH_VERSION}/{caminho}"


def _chamar(metodo: str, caminho: str, token: str = "", **kwargs) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        resposta = requests.request(metodo, _url(caminho), headers=headers, timeout=15, **kwargs)
    except requests.RequestException as exc:
        raise ErroMeta("Falha de comunicação com a Meta. Tente de novo em instantes.") from exc
    try:
        dados = resposta.json()
    except ValueError:
        dados = {}
    if resposta.status_code >= 400 or "error" in dados:
        erro = dados.get("error") or {}
        mensagem = erro.get("error_user_msg") or erro.get("message") or f"Erro {resposta.status_code} da Meta."
        raise ErroMeta(mensagem, codigo=erro.get("code"))
    return dados


def trocar_code(code: str) -> str:
    """Troca o `code` do Embedded Signup pelo token da clínica (business
    integration system user — não expira)."""
    dados = _chamar("GET", "oauth/access_token", params={
        "client_id": settings.META_APP_ID, "client_secret": settings.META_APP_SECRET, "code": code,
    })
    if not dados.get("access_token"):
        raise ErroMeta("A Meta não devolveu o token de acesso.")
    return dados["access_token"]


def assinar_webhooks(waba_id: str, token: str):
    _chamar("POST", f"{waba_id}/subscribed_apps", token)


def remover_webhooks(waba_id: str, token: str):
    _chamar("DELETE", f"{waba_id}/subscribed_apps", token)


def registrar_numero(phone_number_id: str, token: str, pin: str):
    _chamar("POST", f"{phone_number_id}/register", token, json={"messaging_product": "whatsapp", "pin": pin})


def sincronizar_app_business(phone_number_id: str, token: str):
    """Coexistência: puxa contatos e histórico do app WhatsApp Business pra
    Cloud API. Obrigatório em até 24h depois da conexão (senão a clínica tem
    que desconectar e refazer) e só pode ser feito uma vez por conexão."""
    for tipo in ("smb_app_state_sync", "history"):
        _chamar("POST", f"{phone_number_id}/smb_app_data", token, json={"messaging_product": "whatsapp", "sync_type": tipo})


def dados_numero(phone_number_id: str, token: str) -> dict:
    return _chamar("GET", phone_number_id, token, params={"fields": "display_phone_number,verified_name,quality_rating"})


def listar_modelos(waba_id: str, token: str) -> list:
    dados = _chamar("GET", f"{waba_id}/message_templates", token, params={
        "fields": "name,status,category,language,rejected_reason", "limit": 200,
    })
    return [m for m in dados.get("data", []) if m.get("language") == IDIOMA]


def criar_modelo(waba_id: str, token: str, modelo) -> dict:
    return _chamar("POST", f"{waba_id}/message_templates", token, json=modelo.payload_criacao())


def enviar_modelo(phone_number_id: str, token: str, numero: str, modelo, parametros) -> str:
    dados = _chamar("POST", f"{phone_number_id}/messages", token, json={
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "template",
        "template": {
            "name": modelo.nome,
            "language": {"code": IDIOMA},
            "components": [
                {"type": "body", "parameters": [{"type": "text", "text": p} for p in parametros]},
            ],
        },
    })
    return ((dados.get("messages") or [{}])[0]).get("id", "")
