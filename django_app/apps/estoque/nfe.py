"""Parser de NF-e (ENCAT/CONFAZ) pra importação de estoque — porte de
backend/app/nfe.py, namespace-agnostic, aceita <nfeProc> completo ou <NFe>
avulsa. Passa a capturar também o NCM de cada item (código de produto usado
no cálculo de imposto — ver atualização do plano)."""
import xml.etree.ElementTree as ET
from datetime import date


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
            quantidade = float(_texto(prod, "qCom", "0"))
        except ValueError:
            quantidade = 0.0
        try:
            valor_unitario = float(_texto(prod, "vUnCom", "0"))
        except ValueError:
            valor_unitario = 0.0

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
            "quantidade": quantidade,
            "valor_unitario": valor_unitario,
            "lote": lote,
            "validade": validade,
        })

    if not itens:
        raise NFeInvalidaError("Nenhum item encontrado na NF-e.")

    return itens
