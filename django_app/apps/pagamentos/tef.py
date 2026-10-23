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
    # Estorno que ainda precisa ser concluído na maquininha (Vero: o CANCEL vira
    # uma nova requisição que o operador confirma no terminal).
    id_estorno: str = ""

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

    def vincular_terminal(self, *, documento: str, terminal_codigo: str) -> None:
        """Liga uma maquininha da clínica ao Vettro. Provedor sem esse passo não faz nada."""


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


class ErroVero(Exception):
    pass


class VeroClientePDVBackend(TEFBackendBase):
    """Vero (Banrisul) — app "Vero Cliente PDV" na Smart POS + Servidor PDV na
    nuvem (Guia de Integração 1.14, out/2025). Tudo é POST JSON em
    https://pdv.verostore.com.br, sem USB nem programa no computador.

    - `VERO_PDV_TOKEN`: token da integração Vettro, um só para o SaaS (a Vero
      fornece ao cadastrar a integração).
    - CNPJ da clínica (⚙️ Clínica) = `merchantDocumentNumber`, o mesmo da maquininha.
    - Token da maquininha (aparece ao abrir o app) = `terminal_codigo`: vinculado
      pelo Vettro e usado como `group`, o que faz a cobrança abrir sozinha
      naquele terminal.
    - A Vero pede consulta de status no máximo a cada 5s — a tela consulta a
      cada 2s, então `consultar` segura as chamadas pelo cache.
    - O servidor de contingência (IP da maquininha no Wi-Fi) não serve pro
      Vettro: exige estar na mesma rede, e o Vettro roda na nuvem."""

    INTERVALO_CONSULTA = 5

    STATUS = {
        "Disponível": "pendente", "Em andamento": "pendente", "Aprovada": "aprovado",
        "Declinada": "negado", "Não aprovada": "negado", "Falha": "erro",
        "Cancelada (PDV)": "cancelado", "Cancelada (Operador)": "cancelado",
    }

    def __init__(self):
        self.url = getattr(settings, "VERO_URL", "https://pdv.verostore.com.br").rstrip("/")
        self.pdv_token = getattr(settings, "VERO_PDV_TOKEN", "")
        self.pdv_versao = getattr(settings, "VERO_PDV_VERSION", "1.00.00")
        self.cnpj_credenciadora = getattr(settings, "VERO_CNPJ_CREDENCIADORA", "")
        self.imprimir = getattr(settings, "VERO_IMPRIMIR_COMPROVANTE", True)

    def _post(self, endpoint: str, dados: dict) -> dict:
        import requests

        if not self.pdv_token:
            raise ErroVero("VERO_PDV_TOKEN não configurado.")
        resposta = requests.post(f"{self.url}/{endpoint}", json={"pdvToken": self.pdv_token, **dados}, timeout=15)
        try:
            corpo = resposta.json()
        except ValueError:
            corpo = None
        if resposta.status_code >= 400 or not isinstance(corpo, dict):
            raise ErroVero(f"Vero respondeu {resposta.status_code}: {resposta.text[:200]}")
        return corpo

    @staticmethod
    def _documento() -> str:
        from apps.core.models import ConfiguracaoClinica

        documento = "".join(filter(str.isdigit, ConfiguracaoClinica.atual().cnpj or ""))
        if not documento:
            raise ErroVero("Cadastre o CNPJ da clínica em Clínica — é o mesmo da maquininha.")
        return documento

    @staticmethod
    def _metodo(forma: str, parcelas: int) -> str:
        if forma == "pix":
            return "QRCODE_VERO_X"
        if forma == "debito":
            return "DEBIT_UNDEFINED"  # bandeira ou Banricompras; a modalidade Banricompras é escolhida na maquininha
        # Parcelado sem juros pro cliente (a clínica financia), o padrão do balcão.
        return "CREDIT_1X" if parcelas <= 1 else "CREDIT_NX_STORE"

    def vincular_terminal(self, *, documento, terminal_codigo):
        corpo = self._post("apiDeviceLink.php", {
            "merchantDocumentNumber": "".join(filter(str.isdigit, documento)), "deviceToken": terminal_codigo,
        })
        if corpo.get("result") != "Success":
            raise ErroVero(f"A Vero não vinculou a maquininha: {corpo}")

    def iniciar(self, *, valor, forma, parcelas=1, terminal_codigo="", referencia=""):
        dados = {
            "pdvVersion": self.pdv_versao, "merchantDocumentNumber": self._documento(),
            "amount": int((valor * 100).quantize(Decimal("1"))), "method": self._metodo(forma, parcelas),
            "print": self.imprimir, "waitUser": False, "comments": referencia[:60],
        }
        if forma == "credito" and parcelas > 1:
            dados["installments"] = parcelas
        if terminal_codigo:
            dados["group"] = terminal_codigo
        corpo = self._post("apiTransactionCreate.php", dados)
        token = corpo.get("transaction_token")
        if not token:
            return ResultadoTEF(status="erro", mensagem_erro=f"A Vero não criou a cobrança: {corpo}")
        return ResultadoTEF(status="pendente", id_externo=token)

    def consultar(self, transacao):
        from django.core.cache import cache

        pendente = ResultadoTEF(status="pendente", id_externo=transacao.id_externo)
        if not cache.add(f"vero-consulta-{transacao.id_externo}", 1, self.INTERVALO_CONSULTA):
            return pendente
        dados = self._post("apiTransactionQuery.php", {"transactionToken": [transacao.id_externo]}).get(transacao.id_externo)
        if not isinstance(dados, dict):
            return pendente
        status = self.STATUS.get(dados.get("status", ""), "pendente")
        if status != "aprovado":
            mensagem = "" if status == "pendente" else f"Maquininha: {dados.get('status')}."
            return ResultadoTEF(status=status, id_externo=transacao.id_externo, mensagem_erro=mensagem)
        return ResultadoTEF(
            status="aprovado", id_externo=transacao.id_externo, nsu=str(dados.get("nsu", "")),
            codigo_autorizacao=str(dados.get("auth_code", "")),
            bandeira=dados.get("card_brand") or ("PIX" if transacao.forma == "pix" else dados.get("transaction_name", "")),
            adquirente="Vero (Banrisul)", cnpj_credenciadora=self.cnpj_credenciadora,
        )

    def cancelar(self, transacao):
        if transacao.status == "pendente":
            corpo = self._post("apiTransactionCancel.php", {"transactionToken": transacao.id_externo})
            if corpo.get(transacao.id_externo) == "Cancelada (PDV)":
                return ResultadoTEF(status="cancelado", id_externo=transacao.id_externo)
            return ResultadoTEF(status="erro", mensagem_erro=(
                "A cobrança já começou na maquininha — cancele por lá ou aguarde terminar."))
        # Aprovada: o estorno é uma nova requisição (CANCEL + NSU) que abre na
        # maquininha onde a venda foi paga; o operador conclui no terminal.
        dados = {"pdvVersion": self.pdv_versao, "merchantDocumentNumber": self._documento(), "method": "CANCEL",
                 "nsu": transacao.nsu, "print": self.imprimir, "waitUser": False, "comments": "Estorno Vettro"}
        if transacao.terminal_codigo:
            dados["group"] = transacao.terminal_codigo
        token = self._post("apiTransactionCreate.php", dados).get("transaction_token")
        if not token:
            return ResultadoTEF(status="erro", mensagem_erro="A Vero não abriu o estorno na maquininha.")
        return ResultadoTEF(status="estornado", id_externo=transacao.id_externo, id_estorno=token)


def get_tef_backend() -> TEFBackendBase:
    caminho = getattr(settings, "TEF_BACKEND", "apps.pagamentos.tef.TEFConsoleBackend")
    return import_string(caminho)()
