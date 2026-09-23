"""Rate limiter em memória (adequado para o único processo uvicorn deste deploy —
ver Dockerfile.prod, sem --workers). Protege contra força bruta no login."""

import time
from collections import defaultdict

JANELA_SEGUNDOS = 15 * 60
MAX_TENTATIVAS = 5

_tentativas: dict[str, list[float]] = defaultdict(list)


def registrar_falha(chave: str):
    agora = time.monotonic()
    _tentativas[chave] = [t for t in _tentativas[chave] if agora - t < JANELA_SEGUNDOS] + [agora]


def limpar(chave: str):
    _tentativas.pop(chave, None)


def bloqueado(chave: str) -> bool:
    agora = time.monotonic()
    tentativas = [t for t in _tentativas.get(chave, []) if agora - t < JANELA_SEGUNDOS]
    _tentativas[chave] = tentativas
    return len(tentativas) >= MAX_TENTATIVAS
