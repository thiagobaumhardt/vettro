"""Cifra o token de acesso da Meta de cada clínica antes de gravar no banco —
quem tem o token manda mensagem em nome da clínica, então não fica em texto
puro. Chave em WHATSAPP_CHAVE_CRIPTO (Fernet); sem ela, deriva do SECRET_KEY
(trocar o SECRET_KEY invalida os tokens — aí é só reconectar)."""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet() -> Fernet:
    chave = getattr(settings, "WHATSAPP_CHAVE_CRIPTO", "")
    if not chave:
        chave = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(chave)


def cifrar(texto: str) -> str:
    return _fernet().encrypt(texto.encode()).decode() if texto else ""


def decifrar(cifrado: str) -> str:
    if not cifrado:
        return ""
    try:
        return _fernet().decrypt(cifrado.encode()).decode()
    except InvalidToken:
        return ""
