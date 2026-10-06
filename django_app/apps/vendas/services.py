from collections import OrderedDict
from decimal import Decimal, InvalidOperation

from django.db import connection, transaction
from django.db.models import Max
from django.utils import timezone

from apps.core.models import ConfiguracaoClinica
from apps.estoque.fiscal import tributacao_de_venda
from apps.estoque.services import debitar_para_consumo, estornar_consumo
from apps.financeiro import services as financeiro_services
from apps.financeiro.services import PagamentoInvalidoError

from .models import Venda


class VendaInvalidaError(Exception):
    pass


def usos_do_post(post) -> list[dict]:
    """Linhas paralelas `item_insumo`/`item_qtd`; o mesmo produto em duas
    linhas vira uma só (soma as quantidades)."""
    agregado = OrderedDict()
    for insumo_id, qtd in zip(post.getlist("item_insumo"), post.getlist("item_qtd")):
        if not insumo_id:
            continue
        try:
            qtd_dec = Decimal(str(qtd).replace(",", "."))
        except (TypeError, InvalidOperation) as exc:
            raise VendaInvalidaError("Quantidade inválida.") from exc
        if qtd_dec <= 0:
            raise VendaInvalidaError("A quantidade de cada produto deve ser maior que zero.")
        agregado[insumo_id] = agregado.get(insumo_id, Decimal("0")) + qtd_dec
    if not agregado:
        raise VendaInvalidaError("Adicione ao menos um produto.")
    return [{"insumo_id": i, "qtd": q} for i, q in agregado.items()]


def _proximo_numero() -> int:
    with connection.cursor() as cursor:
        cursor.execute(f"LOCK TABLE {Venda._meta.db_table} IN SHARE ROW EXCLUSIVE MODE")
    return (Venda.objects.aggregate(m=Max("numero"))["m"] or 0) + 1


@transaction.atomic
def registrar_venda(*, usos, forma_pagamento, desconto_tipo, desconto_texto, motivo, cliente_nome, usuario) -> Venda:
    """Preço vem sempre do cadastro do produto (não do formulário). Estoque
    insuficiente levanta EstoqueInsuficienteError e desfaz tudo."""
    if forma_pagamento not in dict(Venda.FORMA_PAGAMENTO_CHOICES):
        raise VendaInvalidaError("Escolha a forma de pagamento.")
    itens, subtotal, debitos = financeiro_services.montar_insumos(usos)
    # Tributação de cada item congelada na venda — é o que vai pra NFC-e,
    # mesmo que a regra da clínica ou o produto mudem depois.
    config = ConfiguracaoClinica.atual()
    for item, (insumo, _qtd) in zip(itens, debitos):
        item["fiscal"] = {k: v for k, v in tributacao_de_venda(insumo, config).items() if k != "fonte"}

    texto = (desconto_texto or "").strip().replace(",", ".")
    try:
        informado = Decimal(texto) if texto else Decimal("0")
    except InvalidOperation as exc:
        raise VendaInvalidaError("Valor de desconto inválido.") from exc
    try:
        desconto = financeiro_services.calcular_desconto(subtotal, desconto_tipo or "valor", informado) if informado else Decimal("0")
    except PagamentoInvalidoError as exc:
        raise VendaInvalidaError(str(exc)) from exc
    motivo = (motivo or "").strip()
    if desconto > 0 and not motivo:
        raise VendaInvalidaError("Informe o motivo do desconto.")

    venda = Venda.objects.create(
        numero=_proximo_numero(), cliente_nome=(cliente_nome or "").strip()[:150],
        itens=itens, subtotal=subtotal,
        desconto_tipo=(desconto_tipo or "valor") if desconto > 0 else "",
        desconto_informado=informado if desconto > 0 else None,
        desconto_valor=desconto, desconto_motivo=motivo if desconto > 0 else "",
        total=subtotal - desconto, forma_pagamento=forma_pagamento,
        usuario_nome=getattr(usuario, "nome", ""),
    )
    for insumo, qtd in debitos:
        debitar_para_consumo(
            insumo=insumo, quantidade=qtd, subtipo="venda_produto",
            origem_tipo="venda", origem_id=venda.id, usuario=usuario,
        )
    return venda


def pdf_comprovante(venda: Venda, *, clinica_nome: str) -> bytes:
    """Comprovante de venda (não fiscal — NFC-e segue fora de escopo)."""
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    from apps.core.pdf import ESTILOS, _esc, brl, gerar_pdf, COR_FUNDO, COR_LINHA, COR_LINHA_SUAVE, COR_TEXTO, FONTE_NEGRITO, FONTE_TEXTO

    e = ESTILOS
    corpo = [Paragraph(f"Comprovante de venda nº {venda.numero}", e["titulo"])]
    if venda.cancelada_em:
        corpo.append(Paragraph(
            f"<font color='#A9442B'><b>VENDA CANCELADA em {timezone.localtime(venda.cancelada_em):%d/%m/%Y %H:%M}"
            + (f" por {_esc(venda.cancelada_por_nome)}" if venda.cancelada_por_nome else "") + "</b></font>",
            e["normal"],
        ))
    corpo += [
        Paragraph(f"<b>Data:</b> {timezone.localtime(venda.criado_em):%d/%m/%Y %H:%M}", e["normal"]),
        Paragraph(f"<b>Cliente:</b> {_esc(venda.cliente_nome) or 'Consumidor'}", e["normal"]),
    ]
    if venda.usuario_nome:
        corpo.append(Paragraph(f"<b>Atendido por:</b> {_esc(venda.usuario_nome)}", e["normal"]))
    corpo.append(Spacer(1, 0.5 * cm))

    linhas = [["Produto", "Qtd", "Valor unit.", "Subtotal"]]
    for item in venda.itens:
        qtd = Decimal(str(item["qtd"]))
        linhas.append([
            Paragraph(_esc(item["nome"]), e["normal"]),
            f"{qtd.normalize():f}".replace(".", ",") + (f" {item['unidade']}" if item.get("unidade") and item["unidade"] != "un." else ""),
            brl(item["valor"]), brl(Decimal(item.get("subtotal") or Decimal(item["valor"]) * qtd)),
        ])
    totais = [["", "", "Subtotal", brl(venda.subtotal)]]
    if venda.desconto_valor:
        rotulo = "Desconto" + (f" ({venda.desconto_informado.normalize():f}%)" if venda.desconto_tipo == "percentual" else "")
        totais.append(["", "", rotulo, "− " + brl(venda.desconto_valor)])
    totais.append(["", "", "Total", brl(venda.total)])
    tabela = Table(linhas + totais, colWidths=[9.2 * cm, 1.6 * cm, 3 * cm, 3.2 * cm], repeatRows=1)
    primeira_total = len(linhas)
    tabela.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FONTE_TEXTO), ("TEXTCOLOR", (0, 0), (-1, -1), COR_TEXTO), 
        ("FONTNAME", (0, 0), (-1, 0), FONTE_NEGRITO),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, COR_TEXTO),
        ("LINEBELOW", (0, 1), (-1, primeira_total - 1), 0.3, COR_LINHA_SUAVE),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEABOVE", (2, primeira_total), (-1, primeira_total), 0.8, COR_TEXTO),
        ("FONTNAME", (2, -1), (-1, -1), FONTE_NEGRITO),
        ("FONTSIZE", (2, -1), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    corpo.append(tabela)
    corpo.append(Spacer(1, 0.3 * cm))
    corpo.append(Paragraph(f"<b>Forma de pagamento:</b> {venda.get_forma_pagamento_display()}", e["normal"]))
    if venda.desconto_valor and venda.desconto_motivo:
        corpo.append(Paragraph(f"<b>Motivo do desconto:</b> {_esc(venda.desconto_motivo)}", e["normal"]))
    corpo.append(Paragraph(
        "Comprovante de pagamento emitido pela clínica. <b>Este documento não tem valor fiscal.</b> "
        "Obrigado pela preferência!",
        e["aviso"],
    ))
    return gerar_pdf(
        titulo_documento=f"Comprovante de venda nº {venda.numero}", clinica_nome=clinica_nome,
        config=ConfiguracaoClinica.atual(), flowables=corpo,
    )


@transaction.atomic
def cancelar_venda(venda: Venda, *, usuario) -> None:
    """Cancelamento mantém o registro (histórico de caixa) e devolve os
    produtos ao estoque."""
    if venda.cancelada_em:
        raise VendaInvalidaError("Esta venda já foi cancelada.")
    from apps.pagamentos.notas import cancelar_da_venda

    estornar_consumo(origem_tipo="venda", origem_id=venda.id, usuario=usuario)
    cancelar_da_venda(venda)
    venda.cancelada_em = timezone.now()
    venda.cancelada_por_nome = getattr(usuario, "nome", "")
    venda.save(update_fields=["cancelada_em", "cancelada_por_nome"])
