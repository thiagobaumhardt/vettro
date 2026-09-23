"""Parser de XML de NF-e (Nota Fiscal Eletrônica) para importação de compras de insumos.

Layout nacional (ENCAT/CONFAZ) — lê os itens (<det><prod>) de dentro de <infNFe>,
seja o arquivo um <nfeProc> completo (nota + protocolo de autorização) ou um <NFe> isolado.
Quando o item é de produto controlado/rastreado (ex: medicamento), o bloco opcional
<rastro> traz lote e validade — não vêm no código de barras, só na nota fiscal.
"""

import datetime as dt
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from fastapi import HTTPException


@dataclass
class ItemNfe:
    codigo_barras: str | None
    nome: str
    quantidade: float
    valor_unitario: float
    lote: str | None = None
    validade: dt.date | None = None


def _sem_namespace(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _achar(el: ET.Element, caminho: str) -> ET.Element | None:
    """Busca um elemento filho por caminho, ignorando namespace (ex: 'prod/xProd')."""
    atual = el
    for parte in caminho.split("/"):
        proximo = None
        for filho in atual:
            if _sem_namespace(filho.tag) == parte:
                proximo = filho
                break
        if proximo is None:
            return None
        atual = proximo
    return atual


def _texto(el: ET.Element, caminho: str) -> str | None:
    achado = _achar(el, caminho)
    return achado.text.strip() if achado is not None and achado.text else None


def parsear_nfe(conteudo: bytes) -> list[ItemNfe]:
    try:
        root = ET.fromstring(conteudo)
    except ET.ParseError:
        raise HTTPException(status_code=400, detail="Arquivo XML inválido ou corrompido.")

    infnfe = None
    for el in root.iter():
        if _sem_namespace(el.tag) == "infNFe":
            infnfe = el
            break
    if infnfe is None:
        raise HTTPException(status_code=400, detail="Este arquivo não parece ser uma NF-e (tag infNFe não encontrada).")

    itens = []
    for det in infnfe:
        if _sem_namespace(det.tag) != "det":
            continue
        prod = _achar(det, "prod")
        if prod is None:
            continue

        nome = _texto(prod, "xProd")
        if not nome:
            continue

        cean = _texto(prod, "cEAN") or _texto(prod, "cEANTrib")
        if cean in ("SEM GTIN", "SEMGTIN", ""):
            cean = None

        try:
            qtd = float(_texto(prod, "qCom") or "0")
            valor_unit = float(_texto(prod, "vUnCom") or "0")
        except ValueError:
            qtd, valor_unit = 0.0, 0.0

        lote = None
        validade = None
        rastro = _achar(prod, "rastro")
        if rastro is not None:
            lote = _texto(rastro, "nLote")
            d_val = _texto(rastro, "dVal")
            if d_val:
                try:
                    validade = dt.date.fromisoformat(d_val[:10])
                except ValueError:
                    validade = None

        itens.append(
            ItemNfe(
                codigo_barras=cean,
                nome=nome,
                quantidade=qtd,
                valor_unitario=valor_unit,
                lote=lote,
                validade=validade,
            )
        )

    if not itens:
        raise HTTPException(status_code=400, detail="Nenhum item de produto encontrado nesta NF-e.")
    return itens
