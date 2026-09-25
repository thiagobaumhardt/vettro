"""Camada de maquininha — interface substituível, mesmo princípio usado pro
WhatsApp (apps.agenda.notificacoes): o Vettro não fala com Sicredi/Stone/
Cielo diretamente, fala com uma casa TEF agnóstica de adquirente (SiTef ou
PayGo — decisão ainda em aberto, ver §8 do plano), então o backend real
disso é plugável sem afetar `services.py` nem as views.

Enquanto o contrato/homologação com a casa TEF escolhida não existe,
`TEFConsoleBackend` (sandbox, sempre aprova) é o padrão — permite testar o
fluxo completo (Cobrança → TEF → Cobrança paga) sem depender de setup
externo, igual o `WhatsAppConsoleBackend` fez pro lembrete."""
import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger("vettro.tef")


@dataclass
class ResultadoTEF:
    aprovado: bool
    status: str  # "aprovado" | "negado" | "erro" | "cancelado"
    nsu: str = ""
    codigo_autorizacao: str = ""
    bandeira: str = ""
    mensagem_erro: str = ""


class TEFBackendBase:
    def cobrar(self, *, valor: Decimal, parcelas: int = 1, terminal_codigo: str = "") -> ResultadoTEF:
        raise NotImplementedError


class TEFConsoleBackend(TEFBackendBase):
    """Sandbox — não fala com maquininha nenhuma, sempre aprova na hora.
    Backend padrão até a clínica ter TEF de verdade configurado."""

    def cobrar(self, *, valor: Decimal, parcelas: int = 1, terminal_codigo: str = "") -> ResultadoTEF:
        logger.info(
            "TEF (console, sandbox) aprovando R$ %s em %sx (terminal=%s) — nenhuma maquininha real foi chamada.",
            valor, parcelas, terminal_codigo or "padrão",
        )
        return ResultadoTEF(
            aprovado=True, status="aprovado",
            nsu=f"SANDBOX-{uuid.uuid4().hex[:8].upper()}",
            codigo_autorizacao="000000", bandeira="sandbox",
        )


def get_tef_backend() -> TEFBackendBase:
    caminho = getattr(settings, "TEF_BACKEND", "apps.pagamentos.tef.TEFConsoleBackend")
    return import_string(caminho)()
