"""Tributação de cada produto na venda de balcão (NFC-e).

Ninguém cadastra CFOP/CSOSN produto por produto: eles dependem do tipo de
venda, não do produto. A clínica guarda duas linhas de regra (produto normal
e produto com substituição tributária) e o produto só informa se tem ST — o
que vem do XML do fornecedor. CFOP/CSOSN preenchidos no produto funcionam
como exceção pontual."""


def tributacao_de_venda(insumo, config) -> dict:
    """`config` = core.ConfiguracaoClinica. Retorna os códigos que vão pra NFC-e
    e de onde vieram (`fonte`), pra tela mostrar quando é exceção."""
    if insumo.tem_st:
        cfop, cst_csosn, fonte = config.cfop_venda_st, config.cst_csosn_venda_st, "regra com substituição tributária"
    else:
        cfop, cst_csosn, fonte = config.cfop_venda, config.cst_csosn_venda, "regra da clínica"
    if insumo.cfop or insumo.cst_csosn:
        fonte = "exceção do produto"
    return {
        "ncm": insumo.ncm or "",
        "origem": insumo.origem or "0",
        "cfop": insumo.cfop or cfop,
        "cst_csosn": insumo.cst_csosn or cst_csosn,
        "tem_st": insumo.tem_st,
        "fonte": fonte,
    }
