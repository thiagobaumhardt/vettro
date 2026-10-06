"""Parser de NF-e (ENCAT/CONFAZ) pra importação de estoque — porte de
backend/app/nfe.py, namespace-agnostic, aceita <nfeProc> completo ou <NFe>
avulsa. Captura também os dados fiscais de cada item que a clínica precisa
pra revender o produto (NFC-e): NCM, origem da mercadoria e se o ICMS tem
substituição tributária."""
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal, InvalidOperation


class NFeInvalidaError(Exception):
    pass


def _sem_namespace(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _achar(elemento, nome_tag):
    if elemento is None:
        return None
    for filho in elemento.iter():
        if _sem_namespace(filho.tag) == nome_tag:
            return filho
    return None


def _achar_todos(elemento, nome_tag):
    return [e for e in elemento.iter() if _sem_namespace(e.tag) == nome_tag]


def _texto(elemento, nome_tag, default=None):
    achado = _achar(elemento, nome_tag)
    return achado.text if achado is not None and achado.text else default


# CST (regime normal) e CSOSN (Simples Nacional) que indicam ICMS com
# substituição tributária — o ICMS da revenda já foi recolhido antes, e a
# clínica revende com a regra "com ST" (em geral CFOP 5405 / CSOSN 500).
CST_COM_ST = {"10", "30", "60", "70"}
CSOSN_COM_ST = {"201", "202", "203", "500"}


def _tributacao_icms(det) -> dict:
    """Lê o grupo <ICMS> do item: origem da mercadoria (0 = nacional, 1/2 =
    estrangeira...) e se há substituição tributária."""
    icms = _achar(det, "ICMS")
    grupo = next(iter(icms), None) if icms is not None else None
    if grupo is None:
        return {"origem": None, "tem_st": False}
    cst, csosn = _texto(grupo, "CST"), _texto(grupo, "CSOSN")
    try:
        valor_st = Decimal(_texto(grupo, "vICMSST", "0")) + Decimal(_texto(grupo, "vICMSSTRet", "0"))
    except InvalidOperation:
        valor_st = Decimal("0")
    tem_st = cst in CST_COM_ST or csosn in CSOSN_COM_ST or (cst == "90" and valor_st > 0)
    return {"origem": _texto(grupo, "orig"), "tem_st": tem_st}


def parsear_nfe(conteudo_xml: bytes) -> list[dict]:
    try:
        raiz = ET.fromstring(conteudo_xml)
    except ET.ParseError as exc:
        raise NFeInvalidaError("XML inválido.") from exc

    inf_nfe = _achar(raiz, "infNFe")
    if inf_nfe is None:
        raise NFeInvalidaError("Tag <infNFe> não encontrada — XML não parece ser uma NF-e.")

    itens = []
    for det in _achar_todos(inf_nfe, "det"):
        prod = _achar(det, "prod")
        if prod is None:
            continue

        nome = _texto(prod, "xProd", "")
        codigo_barras = _texto(prod, "cEAN") or _texto(prod, "cEANTrib")
        if codigo_barras in ("SEM GTIN", "SEMGTIN", ""):
            codigo_barras = None
        ncm = _texto(prod, "NCM")

        try:
            quantidade = Decimal(_texto(prod, "qCom", "0"))
        except InvalidOperation:
            quantidade = Decimal("0")
        try:
            valor_unitario = Decimal(_texto(prod, "vUnCom", "0"))
        except InvalidOperation:
            valor_unitario = Decimal("0")

        lote, validade = None, None
        rastro = _achar(det, "rastro")
        if rastro is not None:
            lote = _texto(rastro, "nLote")
            data_val_texto = _texto(rastro, "dVal")
            if data_val_texto:
                try:
                    validade = date.fromisoformat(data_val_texto)
                except ValueError:
                    validade = None

        itens.append({
            "nome": nome,
            "codigo_barras": codigo_barras,
            "ncm": ncm,
            **_tributacao_icms(det),
            "quantidade": quantidade,
            "valor_unitario": valor_unitario,
            # Unidade comercial da nota (CX, UN, FR...) — a quantidade e o
            # valor unitário da NF-e estão nela, não na unidade de uso.
            "unidade_comercial": _texto(prod, "uCom", ""),
            "lote": lote,
            "validade": validade,
        })

    if not itens:
        raise NFeInvalidaError("Nenhum item encontrado na NF-e.")

    return itens
