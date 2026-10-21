"""Camada de maquininha — interface substituível, mesmo princípio usado pro
WhatsApp (apps.whatsapp.backends) e pra nota fiscal (apps.pagamentos.notas).

Por que existe: no RS (Decreto 56.670, desde 01/01/2024) a NFC-e de venda
paga com cartão ou Pix tem que sair com os dados do pagamento preenchidos
pelo sistema integrado à maquininha (bandeira, autorização, CNPJ da
credenciadora — `tpIntegra=1`), sem digitação manual.

O fluxo é ASSÍNCRONO, como nas maquininhas integradas de verdade (Stone
Connect, Mercado Pago Point, SiTef/PayGo): o Vettro ENVIA o valor pra
maquininha (`iniciar`), o cliente passa o cartão/lê o Pix lá, e o Vettro
CONSULTA o resultado (`consultar`) até sair de "pendente". Consulta em vez de
webhook porque a clínica é resolvida pela sessão (domínio único), não pela URL.

Enquanto não há contrato com o provedor, `TEFConsoleBackend` (sandbox) é o
padrão: aprova alguns segundos depois de enviar — dá pra ver a tela de
"aguardando maquininha" funcionando. Valor terminado em ,99 é NEGADO, pra
testar o caminho da recusa. Trocar de provedor = mudar a setting TEF_BACKEND."""
import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from django.utils.module_loading import import_string

logger = logging.getLogger("vettro.tef")


@dataclass
class ResultadoTEF:
    status: str  # "pendente" | "aprovado" | "negado" | "erro" | "cancelado"
    id_externo: str = ""
    nsu: str = ""
    codigo_autorizacao: str = ""
    bandeira: str = ""
    adquirente: str = ""
    cnpj_credenciadora: str = ""
    mensagem_erro: str = ""

    @property
    def aprovado(self) -> bool:
        return self.status == "aprovado"


class TEFBackendBase:
    sandbox = False

    def iniciar(self, *, valor: Decimal, forma: str, parcelas: int = 1, terminal_codigo: str = "",
                referencia: str = "") -> ResultadoTEF:
        """Envia a cobrança pra maquininha. Normalmente volta "pendente" com
        o `id_externo` pra consultar depois."""
        raise NotImplementedError

    def consultar(self, transacao) -> ResultadoTEF:
        raise NotImplementedError

    def cancelar(self, transacao) -> ResultadoTEF:
        """Aborta uma cobrança pendente, ou estorna uma aprovada."""
        raise NotImplementedError


class TEFConsoleBackend(TEFBackendBase):
    """Sandbox — não fala com maquininha nenhuma."""

    sandbox = True
    SEGUNDOS_ATE_RESPONDER = 4

    def iniciar(self, *, valor, forma, parcelas=1, terminal_codigo="", referencia=""):
        logger.info("TEF (sandbox) enviando R$ %s (%s, %sx, terminal=%s, ref=%s) — nenhuma maquininha real foi chamada.",
                    valor, forma, parcelas, terminal_codigo or "padrão", referencia)
        return ResultadoTEF(status="pendente", id_externo=f"SANDBOX-{uuid.uuid4().hex[:12].upper()}")

    def consultar(self, transacao):
        if timezone.now() - transacao.criado_em < timedelta(seconds=self.SEGUNDOS_ATE_RESPONDER):
            return ResultadoTEF(status="pendente", id_externo=transacao.id_externo)
        if transacao.valor % 1 == Decimal("0.99"):
            return ResultadoTEF(status="negado", id_externo=transacao.id_externo,
                                mensagem_erro="Transação negada pelo emissor do cartão (sandbox: valor terminado em ,99).")
        return ResultadoTEF(
            status="aprovado", id_externo=transacao.id_externo,
            nsu=uuid.uuid4().hex[:10].upper(), codigo_autorizacao=f"{uuid.uuid4().int % 10**6:06d}",
            bandeira="PIX" if transacao.forma == "pix" else "VISA", adquirente="Sandbox",
            cnpj_credenciadora="00.000.000/0001-91",
        )

    def cancelar(self, transacao):
        logger.info("TEF (sandbox) cancelando/estornando %s (R$ %s).", transacao.id_externo, transacao.valor)
        return ResultadoTEF(status="cancelado", id_externo=transacao.id_externo)


def get_tef_backend() -> TEFBackendBase:
    caminho = getattr(settings, "TEF_BACKEND", "apps.pagamentos.tef.TEFConsoleBackend")
    return import_string(caminho)()
