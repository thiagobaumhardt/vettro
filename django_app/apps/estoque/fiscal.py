"""Tributação de cada produto na venda de balcão (NFC-e).

Ninguém cadastra CFOP/CSOSN produto por produto: eles dependem do tipo de
venda, não do produto. A clínica guarda duas linhas de regra (produto normal
e produto com substituição tributária) e o produto só informa se tem ST — o
que vem do XML do fornecedor. CFOP/CSOSN preenchidos no produto funcionam
como exceção pontual.

PIS/COFINS segue a mesma ideia: o produto só diz se é monofásico (também vem
do XML). Monofásico sai com CST 04 (revenda a alíquota zero); o resto, com o
CST padrão do regime da clínica — o contador confirma os dois."""

# CST de PIS/COFINS na saída. Simples/MEI: 49 (outras operações de saída — o
# imposto é pago dentro do DAS); Lucro Presumido/Real: 01 (tributável).
CST_PIS_COFINS_MONOFASICO = "04"
CST_PIS_COFINS_POR_REGIME = {"simples": "49", "mei": "49", "presumido": "01", "real": "01"}

SEM_GTIN = "SEM GTIN"


def gtin_nota(codigo_barras: str) -> str:
    """GTIN que vai na nota (cEAN/cEANTrib). Só código GS1 de verdade: 8, 12,
    13 ou 14 dígitos com dígito verificador certo. Código interno — inclusive
    as etiquetas do Vettro (EAN-13 começando com 2, uso restrito) — sai como
    "SEM GTIN", como manda o leiaute fiscal."""
    codigo = (codigo_barras or "").strip()
    if not codigo.isdigit() or len(codigo) not in (8, 12, 13, 14):
        return SEM_GTIN
    if len(codigo) == 13 and codigo.startswith("2"):
        return SEM_GTIN
    corpo, verificador = codigo[:-1], int(codigo[-1])
    soma = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(corpo)))
    return codigo if (10 - soma % 10) % 10 == verificador else SEM_GTIN


def tributacao_de_venda(insumo, config) -> dict:
    """`config` = core.ConfiguracaoClinica. Retorna os códigos que vão pra NFC-e
    e de onde vieram (`fonte`), pra tela mostrar quando é exceção."""
    if insumo.tem_st:
        cfop, cst_csosn, fonte = config.cfop_venda_st, config.cst_csosn_venda_st, "regra com substituição tributária"
    else:
        cfop, cst_csosn, fonte = config.cfop_venda, config.cst_csosn_venda, "regra da clínica"
    if insumo.cfop or insumo.cst_csosn:
        fonte = "exceção do produto"
    if insumo.pis_cofins_monofasico:
        cst_pis_cofins = CST_PIS_COFINS_MONOFASICO
    else:
        cst_pis_cofins = CST_PIS_COFINS_POR_REGIME.get(config.regime_tributario, "49")
    return {
        "codigo": insumo.codigo or "",
        "unidade": insumo.unidade_nota,
        "gtin": gtin_nota(insumo.codigo_barras),
        "ncm": insumo.ncm or "",
        "cest": insumo.cest or "",
        "origem": insumo.origem or "0",
        "cfop": insumo.cfop or cfop,
        "cst_csosn": insumo.cst_csosn or cst_csosn,
        "tem_st": insumo.tem_st,
        "cst_pis_cofins": cst_pis_cofins,
        "pis_cofins_monofasico": insumo.pis_cofins_monofasico,
        "fonte": fonte,
    }
