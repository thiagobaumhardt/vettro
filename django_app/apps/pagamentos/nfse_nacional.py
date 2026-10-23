"""NFS-e direto no Emissor Nacional (Sefin Nacional, padrão gov.br/nfse) —
sem intermediário pago. Ver docs/nfse-nacional.md.

Fluxo: monta a DPS (Declaração de Prestação de Serviço, leiaute 1.01), assina
com o certificado A1 da clínica (XMLDSig, mesmo padrão da NF-e), compacta
(GZip + Base64) e envia por HTTPS com o mesmo certificado (TLS mútuo). A
resposta é síncrona: volta a chave de acesso (50 dígitos) e o XML da NFS-e.

O número da DPS é do Vettro (série + sequência em ConfiguracaoClinica); o
número da NFS-e quem dá é o Emissor Nacional. Se a resposta se perder no
caminho, a próxima tentativa consulta a DPS já enviada (`GET /dps/{id}`) em
vez de mandar outra — assim não sai nota em dobro."""
import base64
import copy
import gzip
import hashlib
import os
import re
import ssl
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from lxml import etree
from requests.adapters import HTTPAdapter

from apps.core.models import ConfiguracaoClinica

from .notas import NotaFiscalBackendBase, NotaFiscalError, ResultadoEmissao

URLS = {
    "producao": "https://sefin.nfse.gov.br/SefinNacional",
    "homologacao": "https://sefin.producaorestrita.nfse.gov.br/SefinNacional",
}
CONSULTA_PUBLICA = "https://www.nfse.gov.br/ConsultaPublica/?tpc=1&chave="
VERSAO_LEIAUTE = "1.01"
VERSAO_APLICATIVO = "Vettro_1.0"

NS = "http://www.sped.fazenda.gov.br/nfse"
DS = "http://www.w3.org/2000/09/xmldsig#"
C14N = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"


def _so_digitos(valor) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def _valor(valor) -> str:
    return f"{Decimal(str(valor)).quantize(Decimal('0.01'))}"


def _brl(valor) -> str:
    texto = f"{Decimal(str(valor)).quantize(Decimal('0.01')):,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------- certificado

@dataclass
class CertificadoA1:
    chave: object
    certificado: object
    titular: str
    cnpj: str
    validade: datetime


def ler_certificado(pfx: bytes, senha: str) -> CertificadoA1:
    """Abre o .pfx do certificado A1. Erros em texto pra mostrar na tela."""
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    try:
        chave, certificado, _ = pkcs12.load_key_and_certificates(pfx, (senha or "").encode())
    except ValueError:
        raise NotaFiscalError("Não foi possível abrir o certificado — confira a senha e se o arquivo é o .pfx (A1).")
    if chave is None or certificado is None:
        raise NotaFiscalError("O arquivo não tem a chave do certificado — use o .pfx (A1) completo.")
    nomes = certificado.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    titular = nomes[0].value if nomes else ""
    # e-CNPJ da ICP-Brasil: CN = "RAZÃO SOCIAL:12345678000199".
    cnpj = _so_digitos(titular.rsplit(":", 1)[-1]) if ":" in titular else ""
    return CertificadoA1(chave=chave, certificado=certificado, titular=titular.split(":")[0],
                         cnpj=cnpj if len(cnpj) == 14 else "", validade=certificado.not_valid_after_utc)


def certificado_da_clinica(config: ConfiguracaoClinica) -> CertificadoA1:
    pfx, senha = config.certificado()
    if not pfx:
        raise NotaFiscalError("Certificado digital da clínica não cadastrado (Configurações da clínica).")
    cert = ler_certificado(pfx, senha)
    if cert.validade < timezone.now():
        raise NotaFiscalError(f"Certificado digital vencido em {timezone.localtime(cert.validade):%d/%m/%Y} — "
                              "cadastre o novo em Configurações da clínica.")
    return cert


# ---------------------------------------------------------------- assinatura

def _el(pai, tag, texto=None, **attrs):
    filho = etree.SubElement(pai, f"{{{NS}}}{tag}", **attrs)
    if texto is not None:
        filho.text = str(texto)
    return filho


def _c14n(elemento) -> bytes:
    """C14N inclusivo do elemento como documento à parte. Aqui o único
    namespace herdado é o padrão (que a cópia mantém), então dá o mesmo
    resultado — e evita um defeito do libxml2, que põe xmlns="" nos filhos
    quando a Signature redeclara o namespace padrão dentro da DPS."""
    return etree.tostring(copy.deepcopy(elemento), method="c14n")


def assinar(raiz, alvo, cert: CertificadoA1) -> None:
    """XMLDSig envelopada sobre `alvo` (infDPS/infPedReg), Signature como
    último filho da raiz: C14N inclusivo, RSA-SHA1 — o padrão aceito pelo
    Emissor Nacional, igual ao da NF-e."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    digest = base64.b64encode(hashlib.sha1(_c14n(alvo)).digest()).decode()
    assinatura = etree.SubElement(raiz, f"{{{DS}}}Signature", nsmap={None: DS})
    info = etree.SubElement(assinatura, f"{{{DS}}}SignedInfo")
    etree.SubElement(info, f"{{{DS}}}CanonicalizationMethod", Algorithm=C14N)
    etree.SubElement(info, f"{{{DS}}}SignatureMethod", Algorithm=f"{DS}rsa-sha1")
    ref = etree.SubElement(info, f"{{{DS}}}Reference", URI="#" + alvo.get("Id"))
    transformacoes = etree.SubElement(ref, f"{{{DS}}}Transforms")
    etree.SubElement(transformacoes, f"{{{DS}}}Transform", Algorithm=f"{DS}enveloped-signature")
    etree.SubElement(transformacoes, f"{{{DS}}}Transform", Algorithm=C14N)
    etree.SubElement(ref, f"{{{DS}}}DigestMethod", Algorithm=f"{DS}sha1")
    etree.SubElement(ref, f"{{{DS}}}DigestValue").text = digest

    valor = cert.chave.sign(_c14n(info), padding.PKCS1v15(), hashes.SHA1())
    etree.SubElement(assinatura, f"{{{DS}}}SignatureValue").text = base64.b64encode(valor).decode()
    x509 = etree.SubElement(etree.SubElement(assinatura, f"{{{DS}}}KeyInfo"), f"{{{DS}}}X509Data")
    der = cert.certificado.public_bytes(serialization.Encoding.DER)
    etree.SubElement(x509, f"{{{DS}}}X509Certificate").text = base64.b64encode(der).decode()


_ESQUEMA = None


def validar_esquema(raiz) -> list[str]:
    """Confere a DPS assinada contra o XSD oficial (apps/pagamentos/xsd_nfse,
    leiaute de 20/10/2026) antes de enviar: erro de leiaute aparece aqui, com
    o campo, em vez de virar um E1235 genérico do Emissor Nacional. Quando o
    governo mudar o leiaute, troque os arquivos dessa pasta."""
    global _ESQUEMA
    if _ESQUEMA is None:
        from pathlib import Path

        _ESQUEMA = etree.XMLSchema(etree.parse(str(Path(__file__).resolve().parent / "xsd_nfse" / "DPS_v1.01.xsd")))
    if _ESQUEMA.validate(raiz):
        return []
    return [f"Leiaute da DPS: {e.message}" for e in list(_ESQUEMA.error_log)[:3]]


def _serializar(raiz) -> bytes:
    return etree.tostring(raiz, xml_declaration=True, encoding="UTF-8")


# ---------------------------------------------------------------- DPS

def _agora():
    # Um minuto pra trás: o Emissor Nacional recusa dhEmi "no futuro" se o
    # relógio do servidor estiver adiantado em relação ao dele.
    return timezone.localtime() - timedelta(minutes=1)


def id_dps(config, numero: int) -> str:
    """"DPS" + município (7) + tipo de inscrição (2 = CNPJ) + CNPJ (14) + série (5) + número (15)."""
    return f"DPS{config.codigo_municipio_ibge}2{_so_digitos(config.cnpj)}{int(config.nfse_serie):05d}{numero:015d}"


def _opcao_simples(regime: str) -> str:
    return {"simples": "3", "mei": "2"}.get(regime, "1")


def descricao_servico(dados: dict) -> str:
    linhas = [dados.get("discriminacao") or "Serviços médico-veterinários"]
    linhas += [f"- {i['descricao']}: {_brl(i['valor'])}" for i in dados.get("itens", [])]
    if dados.get("paciente"):
        linhas.append(f"Paciente: {dados['paciente']}")
    texto = "\n".join(linhas)
    return texto if len(texto) <= 2000 else texto[:1997] + "..."


def validar_nacional(dados: dict, config) -> list[str]:
    erros = []
    if len(config.codigo_municipio_ibge or "") != 7:
        erros.append("Código IBGE do município da clínica não cadastrado (Configurações da clínica — sai pelo CEP).")
    codigos = {i.get("codigo_nacional") for i in dados.get("itens", [])}
    if len(codigos) > 1:
        erros.append("No padrão nacional cada NFS-e tem um só código de tributação, e estes serviços têm códigos "
                     f"diferentes ({', '.join(sorted(c or '—' for c in codigos))}). Emita separado ou ajuste o catálogo.")
    if any(i.get("codigo_municipal") and not re.fullmatch(r"\d{3}", i["codigo_municipal"]) for i in dados.get("itens", [])):
        erros.append("No padrão nacional o código municipal tem 3 dígitos — corrija em Clínica ou no catálogo de Serviços "
                     "(ou deixe em branco se a prefeitura não exige).")
    if config.regime_tributario == "simples" and config.nfse_aliquota_simples is None:
        erros.append("Informe a alíquota aproximada do Simples Nacional (Configurações da clínica — o contador passa).")
    tomador = _so_digitos(dados.get("tomador", {}).get("cpf"))
    if tomador and len(tomador) not in (11, 14):
        erros.append("CPF/CNPJ do tomador inválido.")
    return erros


def montar_dps(dados: dict, config, numero: int, ambiente: str):
    raiz = etree.Element(f"{{{NS}}}DPS", nsmap={None: NS}, versao=VERSAO_LEIAUTE)
    inf = _el(raiz, "infDPS", Id=id_dps(config, numero))
    agora = _agora()
    _el(inf, "tpAmb", "1" if ambiente == "producao" else "2")
    _el(inf, "dhEmi", agora.replace(microsecond=0).isoformat())
    _el(inf, "verAplic", VERSAO_APLICATIVO)
    _el(inf, "serie", str(int(config.nfse_serie)))
    _el(inf, "nDPS", str(numero))
    _el(inf, "dCompet", agora.date().isoformat())
    _el(inf, "tpEmit", "1")  # emitente = o próprio prestador
    # Leiaute de 20/10/2026 (NT 009): finalidade obrigatória — 0 = NFS-e regular.
    _el(inf, "finNFSe", "0")
    _el(inf, "cLocEmi", config.codigo_municipio_ibge)

    # Prestador emitente: nome e endereço NÃO vão (o Emissor Nacional usa o cadastro dele).
    prest = _el(inf, "prest")
    _el(prest, "CNPJ", _so_digitos(config.cnpj))
    if config.inscricao_municipal:
        _el(prest, "IM", config.inscricao_municipal)
    reg = _el(prest, "regTrib")
    opcao = _opcao_simples(config.regime_tributario)
    _el(reg, "opSimpNac", opcao)
    if opcao == "3":
        _el(reg, "regApTribSN", "1")  # tributos federais e ISS apurados pelo Simples
    _el(reg, "regEspTrib", "0")

    tomador = dados.get("tomador", {})
    documento = _so_digitos(tomador.get("cpf"))
    if documento:  # sem CPF = consumidor não identificado (grupo toma omitido)
        toma = _el(inf, "toma")
        _el(toma, "CPF" if len(documento) == 11 else "CNPJ", documento)
        _el(toma, "xNome", (tomador.get("nome") or "Consumidor")[:300])
        email = (tomador.get("email") or "").strip()
        if email and len(email) <= 80:
            _el(toma, "email", email)

    serv = _el(inf, "serv")
    _el(_el(serv, "locPrest"), "cLocPrestacao", config.codigo_municipio_ibge)
    cserv = _el(serv, "cServ")
    item = (dados.get("itens") or [{}])[0]
    _el(cserv, "cTribNac", item.get("codigo_nacional") or config.nfse_codigo_tributacao_nacional)
    if item.get("codigo_municipal"):
        _el(cserv, "cTribMun", item["codigo_municipal"])
    _el(cserv, "xDescServ", descricao_servico(dados))

    valores = _el(inf, "valores")
    _el(_el(valores, "vServPrest"), "vServ", _valor(dados["valor_servicos"]))
    if Decimal(dados.get("desconto") or "0") > 0:
        _el(_el(valores, "vDescCondIncond"), "vDescIncond", _valor(dados["desconto"]))
    trib = _el(valores, "trib")
    trib_mun = _el(trib, "tribMun")
    _el(trib_mun, "tribISSQN", "1")  # operação tributável
    _el(trib_mun, "tpRetISSQN", "2" if dados.get("iss", {}).get("retido") else "1")
    tot = _el(trib, "totTrib")
    if opcao == "3":  # ME/EPP do Simples: percentual aproximado do Simples, indTotTrib não é aceito
        _el(tot, "pTotTribSN", _valor(config.nfse_aliquota_simples or 0))
    else:
        _el(tot, "indTotTrib", "0")
    return raiz, inf


def montar_cancelamento(config, chave: str, codigo: str, justificativa: str, ambiente: str):
    raiz = etree.Element(f"{{{NS}}}pedRegEvento", nsmap={None: NS}, versao=VERSAO_LEIAUTE)
    inf = _el(raiz, "infPedReg", Id=f"PRE{chave}101101")
    _el(inf, "tpAmb", "1" if ambiente == "producao" else "2")
    _el(inf, "verAplic", VERSAO_APLICATIVO)
    _el(inf, "dhEvento", _agora().replace(microsecond=0).isoformat())
    _el(inf, "CNPJAutor", _so_digitos(config.cnpj))
    _el(inf, "chNFSe", chave)
    evento = _el(inf, "e101101")
    _el(evento, "xDesc", "Cancelamento de NFS-e")
    _el(evento, "cMotivo", codigo)  # 1 erro na emissão, 2 serviço não prestado, 9 outros
    _el(evento, "xMotivo", justificativa.ljust(15, ".")[:255])  # mínimo de 15 caracteres
    return raiz, inf


# ---------------------------------------------------------------- comunicação

def compactar(xml: bytes) -> str:
    return base64.b64encode(gzip.compress(xml)).decode("ascii")


def descompactar(b64: str) -> str:
    return gzip.decompress(base64.b64decode(b64)).decode("utf-8")


class _AdaptadorTLS(HTTPAdapter):
    def __init__(self, contexto, **kwargs):
        self._contexto = contexto
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self._contexto
        return super().init_poolmanager(*args, **kwargs)


def _sessao(cert: CertificadoA1) -> requests.Session:
    """Sessão com TLS mútuo. O ssl só lê certificado de arquivo: grava em
    pasta temporária, carrega na memória e apaga na hora."""
    from cryptography.hazmat.primitives import serialization

    contexto = ssl.create_default_context(cafile=getattr(settings, "NFSE_NACIONAL_CA_BUNDLE", "") or requests.certs.where())
    with tempfile.TemporaryDirectory() as pasta:
        caminho_cert, caminho_chave = os.path.join(pasta, "cert.pem"), os.path.join(pasta, "chave.pem")
        with open(caminho_cert, "wb") as f:
            f.write(cert.certificado.public_bytes(serialization.Encoding.PEM))
        with open(caminho_chave, "wb") as f:
            f.write(cert.chave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                             serialization.NoEncryption()))
        contexto.load_cert_chain(caminho_cert, caminho_chave)
    sessao = requests.Session()
    sessao.mount("https://", _AdaptadorTLS(contexto))
    return sessao


def _erros_da_resposta(resposta) -> list[str]:
    try:
        corpo = resposta.json()
    except ValueError:
        return [f"Emissor Nacional respondeu HTTP {resposta.status_code}."]
    erros = corpo.get("erros") or corpo.get("Erros") or []
    if isinstance(erros, dict):
        erros = [erros]
    textos = []
    for e in erros:
        e = {k.lower(): v for k, v in e.items()}
        texto = f"{e.get('codigo', '')} {e.get('descricao', '')}".strip()
        if e.get("complemento"):
            texto += f" ({e['complemento']})"
        textos.append(texto)
    if any(x.startswith("E0037") for x in textos):
        textos.append("O município da clínica ainda não aderiu ao Emissor Nacional — por enquanto emita pelo portal da prefeitura.")
    return textos or [f"Emissor Nacional respondeu HTTP {resposta.status_code}."]


def numero_da_nfse(xml_nfse: str) -> str:
    raiz = etree.fromstring(xml_nfse.encode("utf-8"))
    return raiz.findtext(f".//{{{NS}}}nNFSe") or ""


class NFSeNacionalBackend(NotaFiscalBackendBase):
    """Emissor Nacional com o certificado da própria clínica. Em homologação
    (produção restrita) a nota é de teste: vai pro Emissor Nacional, mas sem
    valor fiscal — por isso `simulacao` acompanha o ambiente."""

    TIMEOUT = 40

    def __init__(self, config: ConfiguracaoClinica | None = None):
        self.config = config or ConfiguracaoClinica.atual()
        self.ambiente = self.config.nfse_ambiente

    @property
    def simulacao(self):
        return self.ambiente != "producao"

    @property
    def url(self):
        return URLS[self.ambiente]

    def _proximo_numero(self) -> int:
        with transaction.atomic():
            config = ConfiguracaoClinica.objects.select_for_update().get(pk=self.config.pk)
            config.nfse_ultimo_dps += 1
            config.save(update_fields=["nfse_ultimo_dps"])
            return config.nfse_ultimo_dps

    def _buscar_nfse(self, sessao, chave) -> ResultadoEmissao:
        resposta = sessao.get(f"{self.url}/nfse/{chave}", timeout=self.TIMEOUT)
        if resposta.status_code != 200:
            return ResultadoEmissao(autorizada=False, erros=_erros_da_resposta(resposta))
        xml = descompactar(resposta.json()["nfseXmlGZipB64"])
        return ResultadoEmissao(autorizada=True, numero=numero_da_nfse(xml), chave_acesso=chave, xml=xml)

    def emitir(self, nota):
        from .notas import validar

        erros = validar(nota.dados, nota.tipo) + validar_nacional(nota.dados, self.config)
        if erros:
            return ResultadoEmissao(autorizada=False, erros=erros)
        try:
            cert = certificado_da_clinica(self.config)
        except NotaFiscalError as exc:
            return ResultadoEmissao(autorizada=False, erros=[str(exc)])
        nota.dados["emissor"] = {"nome": "nfse_nacional", "ambiente": self.ambiente}
        try:
            sessao = _sessao(cert)
            # Tentativa anterior sem resposta: a DPS pode ter virado nota lá.
            if nota.id_dps:
                consulta = sessao.get(f"{self.url}/dps/{nota.id_dps}", timeout=self.TIMEOUT)
                if consulta.status_code == 200 and consulta.json().get("chaveAcesso"):
                    return self._buscar_nfse(sessao, consulta.json()["chaveAcesso"])

            numero = self._proximo_numero()
            raiz, inf = montar_dps(nota.dados, self.config, numero, self.ambiente)
            assinar(raiz, inf, cert)
            erros_leiaute = validar_esquema(raiz)
            if erros_leiaute:
                return ResultadoEmissao(autorizada=False, erros=erros_leiaute)
            nota.id_dps = inf.get("Id")
            nota.save(update_fields=["id_dps"])
            resposta = sessao.post(f"{self.url}/nfse", json={"dpsXmlGZipB64": compactar(_serializar(raiz))},
                                   timeout=self.TIMEOUT)
        except requests.RequestException as exc:
            return ResultadoEmissao(autorizada=False, erros=[
                f"Sem resposta do Emissor Nacional ({exc.__class__.__name__}). Tente de novo — "
                "o Vettro confere se a nota já saiu antes de enviar outra."])
        except Exception as exc:  # nunca deixa a emissão derrubar o recebimento
            return ResultadoEmissao(autorizada=False, erros=[f"Falha ao montar/enviar a NFS-e: {exc}"])

        if resposta.status_code not in (200, 201):
            nota.id_dps = ""  # DPS recusada: a próxima tentativa usa outro número
            nota.save(update_fields=["id_dps"])
            return ResultadoEmissao(autorizada=False, erros=_erros_da_resposta(resposta))
        corpo = resposta.json()
        xml = descompactar(corpo["nfseXmlGZipB64"])
        return ResultadoEmissao(autorizada=True, numero=numero_da_nfse(xml), chave_acesso=corpo["chaveAcesso"], xml=xml)

    def cancelar(self, nota, justificativa, codigo="9"):
        cert = certificado_da_clinica(self.config)
        ambiente = nota.dados.get("emissor", {}).get("ambiente", self.ambiente)
        raiz, inf = montar_cancelamento(self.config, nota.chave_acesso, codigo, justificativa, ambiente)
        assinar(raiz, inf, cert)
        try:
            resposta = _sessao(cert).post(f"{URLS[ambiente]}/nfse/{nota.chave_acesso}/eventos",
                                          json={"pedidoRegistroEventoXmlGZipB64": compactar(_serializar(raiz))},
                                          timeout=self.TIMEOUT)
        except requests.RequestException as exc:
            raise NotaFiscalError(f"Sem resposta do Emissor Nacional ({exc.__class__.__name__}).")
        if resposta.status_code not in (200, 201):
            raise NotaFiscalError(" ".join(_erros_da_resposta(resposta)))
        return descompactar(resposta.json()["eventoXmlGZipB64"])

    def testar_conexao(self) -> str:
        """Confere certificado + TLS mútuo sem emitir nada: consulta uma DPS
        que não existe (404 = conectou e foi autenticado)."""
        cert = certificado_da_clinica(self.config)
        resposta = _sessao(cert).get(f"{self.url}/dps/{id_dps(self.config, 999999999999999)}", timeout=self.TIMEOUT)
        if resposta.status_code in (200, 404):
            return f"Conectado ao Emissor Nacional ({self.ambiente}) com o certificado de {cert.titular}."
        raise NotaFiscalError(" ".join(_erros_da_resposta(resposta)))
