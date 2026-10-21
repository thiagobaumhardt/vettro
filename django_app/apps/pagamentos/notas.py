"""Emissão de nota fiscal — NFS-e (serviço, a partir de uma Cobrança) e NFC-e
(produto, a partir de uma Venda de balcão).

Mesmo princípio do WhatsApp e do TEF: o Vettro monta os dados da nota e um
BACKEND trocável conversa com o emissor. Enquanto a clínica não tem conta
Focus NFe, o padrão é o `NotaFiscalSimulacaoBackend`: valida os dados como o
emissor real faria, gera número e chave FICTÍCIOS e um PDF marcado
"SIMULAÇÃO — SEM VALOR FISCAL". Nada é enviado à prefeitura nem à SEFAZ.
Trocar pela Focus = mudar a setting NOTA_FISCAL_BACKEND."""
import random
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import IntegerField, Max
from django.db.models.functions import Cast
from django.utils import timezone
from django.utils.module_loading import import_string

from apps.core.models import ConfiguracaoClinica

from .models import NotaFiscalEmitida


class NotaFiscalError(Exception):
    pass


@dataclass
class ResultadoEmissao:
    autorizada: bool
    numero: str = ""
    chave_acesso: str = ""
    erros: list = field(default_factory=list)
    xml: str = ""  # XML autorizado, guardado na nota pra contabilidade


class NotaFiscalBackendBase:
    simulacao = False

    def emitir(self, nota: NotaFiscalEmitida) -> ResultadoEmissao:
        raise NotImplementedError

    def cancelar(self, nota: NotaFiscalEmitida, justificativa: str) -> str:
        """Cancela a nota no emissor e devolve o XML do evento de cancelamento."""
        raise NotImplementedError


class NotaFiscalSimulacaoBackend(NotaFiscalBackendBase):
    """Sem valor fiscal. Faz as mesmas checagens básicas que o emissor real
    (dados da clínica, NCM dos produtos) pra o fluxo ser igual ao de verdade.
    Os "XMLs" gerados são um resumo marcado SIMULAÇÃO, não o leiaute oficial."""

    simulacao = True

    def emitir(self, nota):
        erros = validar(nota.dados, nota.tipo)
        if erros:
            return ResultadoEmissao(autorizada=False, erros=erros)
        ultimo = (NotaFiscalEmitida.objects.filter(tipo=nota.tipo, simulacao=True).exclude(numero="").exclude(pk=nota.pk)
                  .aggregate(m=Max(Cast("numero", IntegerField())))["m"])
        numero = str((ultimo or 0) + 1)
        # 44 dígitos como uma chave de acesso real, mas começando por 99 (não é
        # um código de UF válido), pra nunca ser confundida com uma nota real.
        chave = "99" + "".join(random.choice("0123456789") for _ in range(42))
        return ResultadoEmissao(autorizada=True, numero=numero, chave_acesso=chave,
                                xml=_xml_simulado(nota.tipo, numero, chave, nota.dados))

    def cancelar(self, nota, justificativa):
        raiz = ET.Element("CancelamentoSimulado", tipo=nota.tipo, numero=nota.numero, chave=nota.chave_acesso)
        ET.SubElement(raiz, "aviso").text = "SIMULAÇÃO — SEM VALOR FISCAL"
        ET.SubElement(raiz, "justificativa").text = justificativa
        ET.SubElement(raiz, "data").text = timezone.now().isoformat()
        return ET.tostring(raiz, encoding="unicode")


def _xml_simulado(tipo, numero, chave, dados) -> str:
    """Resumo da nota em XML (cabeçalho, itens com códigos fiscais, totais)."""
    raiz = ET.Element("NotaSimulada", tipo=tipo, numero=numero, chave=chave)
    ET.SubElement(raiz, "aviso").text = "SIMULAÇÃO — SEM VALOR FISCAL"
    ET.SubElement(raiz, "emissao").text = timezone.now().isoformat()
    prestador = ET.SubElement(raiz, "emitente")
    for campo in ("cnpj", "razao_social", "cidade", "uf"):
        ET.SubElement(prestador, campo).text = str(dados.get("prestador", {}).get(campo, ""))
    itens = ET.SubElement(raiz, "itens")
    for item in dados.get("itens", []):
        ET.SubElement(itens, "item", {k: str(v) for k, v in item.items() if not isinstance(v, (dict, list))})
    ET.SubElement(raiz, "valor_total").text = str(dados.get("valor_total", ""))
    return ET.tostring(raiz, encoding="unicode")


def get_backend() -> NotaFiscalBackendBase:
    caminho = getattr(settings, "NOTA_FISCAL_BACKEND", "apps.pagamentos.notas.NotaFiscalSimulacaoBackend")
    return import_string(caminho)()


def _prestador(config: ConfiguracaoClinica, clinica_nome: str) -> dict:
    return {
        "nome_fantasia": clinica_nome, "razao_social": config.razao_social, "cnpj": config.cnpj,
        "regime": config.get_regime_tributario_display(), "endereco": config.endereco_completo,
        "cidade": config.cidade, "uf": config.uf, "telefone": config.telefone, "email": config.email,
    }


def validar(dados: dict, tipo: str) -> list[str]:
    erros = []
    prestador = dados.get("prestador", {})
    if not prestador.get("cnpj"):
        erros.append("CNPJ da clínica não cadastrado (Configurações da clínica).")
    if not prestador.get("razao_social"):
        erros.append("Razão social da clínica não cadastrada (Configurações da clínica).")
    if not prestador.get("cidade") or not prestador.get("uf"):
        erros.append("Cidade/UF da clínica não cadastradas (Configurações da clínica).")
    if not dados.get("itens"):
        erros.append("A nota não tem itens.")
    if Decimal(dados.get("valor_total", "0")) <= 0:
        erros.append("O valor da nota precisa ser maior que zero.")
    if tipo == "nfse":
        for item in dados.get("itens", []):
            if len(item.get("codigo_nacional") or "") != 6:
                erros.append(f"Serviço “{item['descricao']}” sem código de tributação nacional (6 dígitos, ex.: 050202 — "
                             "padrão em Clínica, exceção no catálogo de Serviços).")
    if tipo == "nfce":
        for item in dados.get("itens", []):
            if len(item.get("ncm") or "") != 8:
                erros.append(f"Produto “{item['descricao']}” está sem NCM (cadastre no Estoque).")
            if item.get("tem_st") and len(item.get("cest") or "") != 7:
                erros.append(f"Produto “{item['descricao']}” tem ICMS-ST e está sem CEST (cadastre no Estoque).")
        pag = dados.get("pagamento", {})
        # RS, Decreto 56.670: cartão/Pix só com os dados vindos da maquininha integrada.
        if pag.get("forma") in ("debito", "credito", "pix") and not (pag.get("autorizacao") and pag.get("cnpj_credenciadora")):
            erros.append("Pagamento com cartão/Pix sem a confirmação da maquininha integrada (bandeira, "
                         "autorização e CNPJ da credenciadora) — exigência da NFC-e no RS.")
    return erros


def _codigos_nfse(servico, config) -> dict:
    """Código nacional/municipal do item: exceção do serviço ou padrão da clínica."""
    return {
        "codigo_nacional": (servico.codigo_tributacao_nacional if servico else "") or config.nfse_codigo_tributacao_nacional,
        "codigo_municipal": (servico.codigo_servico_municipal if servico else "") or config.nfse_codigo_municipal,
    }


def _dados_nfse(cobranca, config, clinica_nome) -> dict:
    from apps.estoque.models import Insumo
    from apps.financeiro.models import Servico

    tutor = cobranca.paciente.tutor if cobranca.paciente_id else None

    def qtd_texto(item):
        qtd = f"{Decimal(str(item.get('qtd') or 1)).normalize():f}".replace(".", ",")
        return f"{qtd} {item.get('unidade') or ''}".strip()

    # Snapshots antigos não têm "codigo" — busca no catálogo pelo id. Item de
    # cirurgia (tipo de cirurgia, não Serviço) usa os códigos padrão da clínica.
    servicos = Servico.objects.in_bulk([s["id"] for s in cobranca.servicos if s.get("id")], field_name="pk") if cobranca.servicos else {}
    servicos = {str(k): v for k, v in servicos.items()}
    itens = []
    for s in cobranca.servicos:
        servico = servicos.get(str(s.get("id")))
        itens.append({
            "codigo": s.get("codigo") or (servico.codigo if servico else ""),
            "descricao": s["nome"] + (f" ({qtd_texto(s)})" if str(s.get("qtd") or "1") != "1" else ""),
            "valor": s.get("subtotal") or s["valor"],
            **_codigos_nfse(servico, config),
        })
    # Medicamento/insumo aplicado no atendimento é uso interno (sai do estoque
    # como consumo) e entra no valor do SERVIÇO — não vira venda de mercadoria
    # (orientação do contador, docs/perguntas-contador-notas-fiscais.txt).
    insumos = {str(k): v for k, v in Insumo.objects.in_bulk([i["id"] for i in cobranca.insumos if i.get("id")]).items()} if cobranca.insumos else {}
    for i in cobranca.insumos:
        insumo = insumos.get(str(i.get("id")))
        itens.append({
            "codigo": i.get("codigo") or (insumo.codigo if insumo else ""),
            "descricao": f"{i['nome']} ({qtd_texto(i)})",
            "valor": i.get("subtotal") or str(Decimal(i["valor"]) * Decimal(str(i["qtd"]))),
            **_codigos_nfse(None, config),
        })
    valor_servicos = cobranca.total
    desconto = cobranca.desconto_valor or Decimal("0")
    return {
        "prestador": _prestador(config, clinica_nome),
        "tomador": {
            "nome": tutor.nome if tutor else cobranca.tutor_nome, "cpf": tutor.cpf if tutor else "",
            "endereco": tutor.endereco_completo if tutor else "", "email": tutor.email if tutor else "",
        },
        "paciente": cobranca.paciente.nome if cobranca.paciente_id else "",
        "discriminacao": cobranca.obs or "Serviços médico-veterinários",
        "itens": itens, "valor_servicos": str(valor_servicos), "desconto": str(desconto),
        "valor_total": str(valor_servicos - desconto),
        "forma_pagamento": "Pago" if cobranca.status == "pago" else "A receber",
        "iss": _iss(config),
    }


def _iss(config) -> dict:
    """No Simples o ISS é recolhido no DAS. Retenção pelo tomador só acontece
    com empresa obrigada a reter — tutor pessoa física nunca retém."""
    return {"simples_nacional": config.regime_tributario in ("simples", "mei"), "retido": False}


def _dados_nfse_recebimento(rec, config, clinica_nome) -> dict:
    """Uma NFS-e pro recebimento inteiro (todas as cobranças pagas juntas)."""
    cobrancas = list(rec.cobrancas.select_related("paciente"))
    itens = []
    for c in cobrancas:
        parcial = _dados_nfse(c, config, clinica_nome)
        itens += parcial["itens"]
    tutor = rec.tutor
    pacientes = sorted({c.paciente.nome for c in cobrancas if c.paciente_id})
    return {
        "prestador": _prestador(config, clinica_nome),
        "tomador": {
            "nome": tutor.nome if tutor else rec.tutor_nome, "cpf": rec.cpf_nota,
            "endereco": tutor.endereco_completo if tutor else "", "email": tutor.email if tutor else "",
        },
        "paciente": ", ".join(pacientes),
        "discriminacao": "Serviços médico-veterinários",
        "itens": itens, "valor_servicos": str(rec.subtotal), "desconto": str(rec.desconto_valor),
        "valor_total": str(rec.total), "forma_pagamento": rec.formas_texto, "iss": _iss(config),
    }


def _pagamento_nfce(venda) -> dict:
    """Grupo de pagamento da NFC-e (detPag/card). `tp_integra` 1 = integrado à
    maquininha (o que o RS exige pra cartão/Pix)."""
    pag = {"forma": venda.forma_pagamento, "valor": str(venda.total), "parcelas": venda.parcelas}
    transacao = venda.transacao_aprovada
    if transacao:
        pag.update({
            "tp_integra": 1, "cnpj_credenciadora": transacao.cnpj_credenciadora, "bandeira": transacao.bandeira,
            "autorizacao": transacao.codigo_autorizacao, "nsu": transacao.nsu, "terminal": transacao.terminal_codigo,
        })
    return pag


def _dados_nfce(venda, config, clinica_nome) -> dict:
    itens = []
    for i in venda.itens:
        fiscal = i.get("fiscal", {})
        itens.append({
            # Vendas antigas não têm codigo/gtin/unidade fiscal no snapshot.
            "codigo": fiscal.get("codigo") or i.get("codigo", ""), "gtin": fiscal.get("gtin") or "SEM GTIN",
            "descricao": i["nome"], "qtd": str(i["qtd"]), "unidade": fiscal.get("unidade") or i.get("unidade", ""),
            "valor_unitario": i["valor"],
            "valor": i.get("subtotal") or str(Decimal(i["valor"]) * Decimal(str(i["qtd"]))),
            "ncm": fiscal.get("ncm", ""), "cfop": fiscal.get("cfop", ""), "cst_csosn": fiscal.get("cst_csosn", ""),
            "origem": fiscal.get("origem", "0"), "cest": fiscal.get("cest", ""), "tem_st": fiscal.get("tem_st", False),
            "cst_pis_cofins": fiscal.get("cst_pis_cofins", ""),
        })
    return {
        "prestador": _prestador(config, clinica_nome),
        "tomador": {"nome": venda.cliente_nome or "Consumidor não identificado", "cpf": venda.cliente_cpf},
        "itens": itens, "valor_produtos": str(venda.subtotal), "desconto": str(venda.desconto_valor),
        "valor_total": str(venda.total), "pagamento": _pagamento_nfce(venda),
        "forma_pagamento": venda.get_forma_pagamento_display() + (f" em {venda.parcelas}x" if venda.parcelas > 1 else ""),
    }


@transaction.atomic
def emitir(*, cobranca=None, venda=None, recebimento=None, clinica_nome: str, usuario) -> NotaFiscalEmitida:
    """Emite (ou tenta de novo) a nota de uma cobrança paga, de um recebimento
    da recepção ou de uma venda. Uma nota já emitida não é emitida de novo."""
    origem = {"cobranca": cobranca} if cobranca else {"recebimento": recebimento} if recebimento else {"venda": venda}
    tipo = "nfce" if venda else "nfse"
    existente = NotaFiscalEmitida.objects.filter(**origem, status="emitida").first()
    if existente:
        return existente
    if cobranca and cobranca.status != "pago":
        raise NotaFiscalError("A nota de serviço é emitida ao receber o pagamento.")
    if venda and venda.cancelada_em:
        raise NotaFiscalError("Venda cancelada não emite nota.")
    if venda and venda.pagamento_status != "pago":
        raise NotaFiscalError("A nota de venda sai depois que a maquininha aprovar o pagamento.")

    config = ConfiguracaoClinica.atual()
    if cobranca:
        dados = _dados_nfse(cobranca, config, clinica_nome)
    elif recebimento:
        dados = _dados_nfse_recebimento(recebimento, config, clinica_nome)
    else:
        dados = _dados_nfce(venda, config, clinica_nome)
    backend = get_backend()
    nota = NotaFiscalEmitida.objects.filter(**origem, status="erro").first() or NotaFiscalEmitida(**origem, tipo=tipo)
    nota.dados, nota.valor_total, nota.simulacao = dados, Decimal(dados["valor_total"]), backend.simulacao
    nota.save()

    resultado = backend.emitir(nota)
    if resultado.autorizada:
        nota.status, nota.numero, nota.chave_acesso, nota.mensagem_erro = "emitida", resultado.numero, resultado.chave_acesso, ""
        nota.xml = resultado.xml
        nota.emitida_em, nota.emitida_por_nome = timezone.now(), getattr(usuario, "nome", "")
    else:
        nota.status, nota.mensagem_erro = "erro", " ".join(resultado.erros)[:500]
    nota.save()
    return nota


def cancelar_da_venda(venda) -> None:
    """Venda cancelada → nota cancelada junto, guardando o XML do evento.
    (Com a Focus, o cancelamento real tem prazo: 30 min na NFC-e do RS.)"""
    backend = get_backend()
    justificativa = f"Venda {venda.numero} cancelada no sistema"
    for nota in NotaFiscalEmitida.objects.filter(venda=venda, status="emitida"):
        nota.xml_cancelamento = backend.cancelar(nota, justificativa)
        nota.status, nota.cancelada_em = "cancelada", timezone.now()
        nota.save(update_fields=["status", "cancelada_em", "xml_cancelamento"])


def pdf_nota(nota: NotaFiscalEmitida, *, clinica_nome: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    from apps.core.pdf import ESTILOS, _esc, brl, gerar_pdf, COR_FUNDO, COR_LINHA, COR_LINHA_SUAVE, COR_TEXTO, FONTE_NEGRITO, FONTE_TEXTO

    e, d = ESTILOS, nota.dados
    titulo = "NFS-e — Nota Fiscal de Serviço Eletrônica" if nota.tipo == "nfse" else "NFC-e — Nota Fiscal de Consumidor Eletrônica"
    corpo = []
    if nota.simulacao:
        corpo.append(Paragraph(
            "<font color='#A9442B' size='13'><b>SIMULAÇÃO — SEM VALOR FISCAL</b></font><br/>"
            "<font size='9'>Gerada pelo emissor de teste do Vettro. Nada foi enviado à prefeitura nem à SEFAZ.</font>",
            e["aviso"],
        ))
        corpo.append(Spacer(1, 0.3 * cm))
    corpo.append(Paragraph(titulo, e["titulo"]))
    situacao = {"emitida": f"Nº {nota.numero}", "cancelada": f"Nº {nota.numero} — CANCELADA", "erro": "NÃO AUTORIZADA"}.get(nota.status, nota.status)
    corpo.append(Paragraph(f"<b>{situacao}</b>" + (f" · emitida em {timezone.localtime(nota.emitida_em):%d/%m/%Y %H:%M}" if nota.emitida_em else ""), e["normal"]))
    if nota.chave_acesso:
        chave = " ".join(nota.chave_acesso[i:i + 4] for i in range(0, 44, 4))
        corpo.append(Paragraph(f"<b>Chave de acesso:</b> {chave}", e["pequeno"]))
    if nota.status == "erro":
        corpo.append(Paragraph(f"<font color='#A9442B'><b>Motivo:</b> {_esc(nota.mensagem_erro)}</font>", e["normal"]))
    corpo.append(Spacer(1, 0.4 * cm))

    p, t = d.get("prestador", {}), d.get("tomador", {})
    blocos = Table([
        [Paragraph("<b>PRESTADOR / EMITENTE</b>", e["pequeno"]), Paragraph("<b>TOMADOR / DESTINATÁRIO</b>", e["pequeno"])],
        [Paragraph(_esc(p.get("razao_social") or "(razão social não cadastrada)") + f"<br/>CNPJ {_esc(p.get('cnpj') or '—')}<br/>"
                   + _esc(p.get("endereco") or "") + f"<br/>Regime: {_esc(p.get('regime') or '')}", e["normal"]),
         Paragraph(_esc(t.get("nome") or "") + (f"<br/>CPF {_esc(t['cpf'])}" if t.get("cpf") else "")
                   + (f"<br/>{_esc(t['endereco'])}" if t.get("endereco") else "")
                   + (f"<br/>Paciente: {_esc(d['paciente'])}" if d.get("paciente") else ""), e["normal"])],
    ], colWidths=[8.5 * cm, 8.5 * cm])
    blocos.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FONTE_TEXTO), ("TEXTCOLOR", (0, 0), (-1, -1), COR_TEXTO), ("BOX", (0, 0), (-1, -1), 0.6, COR_LINHA),
                                ("INNERGRID", (0, 0), (-1, -1), 0.3, COR_LINHA_SUAVE),
                                ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (-1, 0), COR_FUNDO)]))
    corpo += [blocos, Spacer(1, 0.4 * cm)]

    if nota.tipo == "nfse":
        linhas = [["Cód.", "Discriminação dos serviços", "Cód. nacional", "Valor"]] + [
            [i.get("codigo") or "—", Paragraph(_esc(i["descricao"]), e["normal"]), i.get("codigo_nacional") or "—", brl(i["valor"])]
            for i in d.get("itens", [])]
        larguras = [1.8 * cm, 9.7 * cm, 2.3 * cm, 3.2 * cm]
    else:
        linhas = [["Cód.", "Produto", "NCM", "CFOP", "CSOSN", "Qtd", "Total"]] + [
            [i.get("codigo") or "—", Paragraph(_esc(i["descricao"]), e["normal"]), i.get("ncm") or "—", i.get("cfop", ""), i.get("cst_csosn", ""),
             f"{Decimal(i['qtd']).normalize():f}".replace(".", ",") + (f" {i['unidade']}" if i.get("unidade") and i["unidade"] != "un." else ""),
             brl(i["valor"])] for i in d.get("itens", [])]
        larguras = [1.3 * cm, 5.3 * cm, 2 * cm, 1.4 * cm, 1.5 * cm, 2.2 * cm, 3.3 * cm]
    tabela = Table(linhas, colWidths=larguras, repeatRows=1)
    tabela.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FONTE_TEXTO), ("TEXTCOLOR", (0, 0), (-1, -1), COR_TEXTO), ("FONTNAME", (0, 0), (-1, 0), FONTE_NEGRITO), ("FONTSIZE", (0, 0), (-1, -1), 9),
                                ("LINEBELOW", (0, 0), (-1, 0), 0.8, COR_TEXTO), ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                                ("LINEBELOW", (0, 1), (-1, -1), 0.3, COR_LINHA_SUAVE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    corpo.append(tabela)

    bruto = d.get("valor_servicos") or d.get("valor_produtos") or d.get("valor_total")
    totais = [["Valor bruto", brl(bruto)]]
    if Decimal(d.get("desconto") or "0") > 0:
        totais.append(["Desconto", "− " + brl(d["desconto"])])
    totais.append(["VALOR TOTAL DA NOTA", brl(d.get("valor_total", "0"))])
    tab_totais = Table(totais, colWidths=[13 * cm, 4 * cm])
    tab_totais.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FONTE_TEXTO), ("TEXTCOLOR", (0, 0), (-1, -1), COR_TEXTO), ("ALIGN", (0, 0), (-1, -1), "RIGHT"), ("FONTNAME", (0, -1), (-1, -1), FONTE_NEGRITO),
                                    ("LINEABOVE", (0, -1), (-1, -1), 0.8, COR_TEXTO)]))
    corpo += [Spacer(1, 0.2 * cm), tab_totais, Spacer(1, 0.3 * cm),
              Paragraph(f"<b>Forma de pagamento:</b> {_esc(d.get('forma_pagamento', ''))}", e["normal"])]
    pag = d.get("pagamento", {})
    if pag.get("autorizacao"):
        corpo.append(Paragraph(
            f"<b>Pagamento integrado:</b> {_esc(pag.get('bandeira', ''))} · Autorização {_esc(pag['autorizacao'])}"
            f" · NSU {_esc(pag.get('nsu', ''))} · Credenciadora CNPJ {_esc(pag.get('cnpj_credenciadora', ''))}", e["pequeno"]))
    return gerar_pdf(titulo_documento=f"{nota.get_tipo_display()} {nota.numero or ''}".strip(), clinica_nome=clinica_nome,
                     config=ConfiguracaoClinica.atual(), flowables=corpo)
