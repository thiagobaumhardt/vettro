from decimal import Decimal, InvalidOperation

from django.db import connection, transaction
from django.db.models import Max
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

from apps.core.models import ConfiguracaoClinica
from apps.core.pdf import ESTILOS, brl, gerar_pdf, COR_FUNDO, COR_LINHA, COR_LINHA_SUAVE, COR_TEXTO, FONTE_NEGRITO, FONTE_TEXTO

from .models import Orcamento

MAX_ITENS = 60


class OrcamentoInvalidoError(Exception):
    pass


def itens_do_post(post) -> list[dict]:
    """Lê as linhas `item_descricao`/`item_qtd`/`item_valor` (listas paralelas)
    e ignora linhas totalmente vazias."""
    itens = []
    linhas = zip(post.getlist("item_descricao"), post.getlist("item_qtd"), post.getlist("item_valor"))
    for descricao, qtd, valor in linhas:
        descricao = descricao.strip()
        if not descricao and not valor.strip():
            continue
        try:
            qtd_dec = Decimal((qtd or "1").replace(",", "."))
            valor_dec = Decimal((valor or "0").replace(",", "."))
        except (ValueError, InvalidOperation) as exc:
            raise OrcamentoInvalidoError(f"Quantidade ou valor inválido no item “{descricao}”.") from exc
        if not descricao:
            raise OrcamentoInvalidoError("Todo item precisa de uma descrição.")
        if qtd_dec <= 0 or valor_dec < 0:
            raise OrcamentoInvalidoError(f"Quantidade ou valor inválido no item “{descricao}”.")
        itens.append({
            "descricao": descricao[:200], "qtd": f"{qtd_dec.normalize():f}",
            "valor": str(valor_dec.quantize(Decimal("0.01"))),
        })
    if not itens:
        raise OrcamentoInvalidoError("Adicione ao menos um item ao orçamento.")
    if len(itens) > MAX_ITENS:
        raise OrcamentoInvalidoError(f"Máximo de {MAX_ITENS} itens por orçamento.")
    return itens


def _proximo_numero() -> int:
    with connection.cursor() as cursor:
        cursor.execute(f"LOCK TABLE {Orcamento._meta.db_table} IN SHARE ROW EXCLUSIVE MODE")
    return (Orcamento.objects.aggregate(m=Max("numero"))["m"] or 0) + 1


@transaction.atomic
def criar_orcamento(*, tutor, paciente, itens, valido_ate, obs, usuario) -> Orcamento:
    total = sum((Decimal(i["valor"]) * Decimal(str(i["qtd"]))).quantize(Decimal("0.01")) for i in itens)
    return Orcamento.objects.create(
        numero=_proximo_numero(), tutor=tutor, paciente=paciente,
        tutor_nome=tutor.nome, tutor_tel=tutor.tel, pac_nome=paciente.nome if paciente else "",
        itens=itens, total=total, valido_ate=valido_ate, obs=obs,
        usuario_nome=getattr(usuario, "nome", ""),
    )


def pdf_orcamento(orcamento: Orcamento, *, clinica_nome: str) -> bytes:
    e = ESTILOS
    corpo = [
        Paragraph(f"Orçamento nº {orcamento.numero}", e["titulo"]),
        Paragraph(f"<b>Tutor:</b> {escape(orcamento.tutor_nome)}"
                  + (f" · {escape(orcamento.tutor_tel)}" if orcamento.tutor_tel else ""), e["normal"]),
    ]
    if orcamento.pac_nome:
        corpo.append(Paragraph(f"<b>Paciente:</b> {escape(orcamento.pac_nome)}", e["normal"]))
    corpo += [
        Paragraph(f"<b>Emitido em:</b> {timezone.localtime(orcamento.criado_em):%d/%m/%Y}", e["normal"]),
        Spacer(1, 0.5 * cm),
    ]

    linhas = [["Descrição", "Qtd", "Valor unit.", "Subtotal"]]
    for item in orcamento.itens:
        qtd = Decimal(str(item["qtd"]))
        linhas.append([
            Paragraph(escape(item["descricao"]), e["normal"]), f"{qtd.normalize():f}".replace(".", ","),
            brl(item["valor"]), brl((Decimal(item["valor"]) * qtd).quantize(Decimal("0.01"))),
        ])
    linhas.append(["", "", "Total", brl(orcamento.total)])
    tabela = Table(linhas, colWidths=[9.2 * cm, 1.6 * cm, 3 * cm, 3.2 * cm], repeatRows=1)
    tabela.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FONTE_TEXTO), ("TEXTCOLOR", (0, 0), (-1, -1), COR_TEXTO), 
        ("FONTNAME", (0, 0), (-1, 0), FONTE_NEGRITO),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, COR_TEXTO),
        ("LINEBELOW", (0, 1), (-1, -2), 0.3, COR_LINHA_SUAVE),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (2, -1), (-1, -1), FONTE_NEGRITO),
        ("LINEABOVE", (2, -1), (-1, -1), 0.8, COR_TEXTO),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    corpo.append(tabela)

    if orcamento.obs:
        corpo += [Spacer(1, 0.4 * cm), Paragraph(f"<b>Observações:</b> {escape(orcamento.obs)}".replace("\n", "<br/>"), e["normal"])]

    corpo.append(Paragraph(
        "<b>Os valores acima são de orçamento</b> — uma estimativa dos custos, e não uma cobrança. "
        "Podem sofrer alteração conforme a avaliação clínica do paciente, intercorrências ou "
        "procedimentos adicionais necessários, que serão comunicados ao tutor antes de realizados. "
        f"<b>Este orçamento é válido até {orcamento.valido_ate:%d/%m/%Y}.</b>",
        e["aviso"],
    ))
    return gerar_pdf(
        titulo_documento=f"Orçamento nº {orcamento.numero}", clinica_nome=clinica_nome,
        config=ConfiguracaoClinica.atual(), flowables=corpo,
    )
