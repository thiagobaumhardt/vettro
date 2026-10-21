"""Etiquetas de produto em folhas Pimaco (impressora comum, jato de tinta ou
laser, papel Carta, escala 100%) — nome, preço e código de barras. Produto sem
código ganha um EAN-13 interno (prefixo 2, reservado pra uso da loja)."""
from io import BytesIO

from django.db import transaction
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

from .models import Insumo

# Medidas oficiais (equivalentes Avery 5160/5161/5162/5163/5167), em mm.
MODELOS = {
    "6080": {"nome": "Pimaco 6080 — 66,7 × 25,4 mm (30 por folha)", "largura": 66.675, "altura": 25.4,
             "colunas": 3, "linhas": 10, "margem_esq": 4.7625, "margem_topo": 12.7, "gap_h": 3.175, "gap_v": 0},
    "6081": {"nome": "Pimaco 6081 — 101,6 × 25,4 mm (20 por folha)", "largura": 101.6, "altura": 25.4,
             "colunas": 2, "linhas": 10, "margem_esq": 3.96875, "margem_topo": 12.7, "gap_h": 4.7625, "gap_v": 0},
    "6082": {"nome": "Pimaco 6082 — 101,6 × 33,9 mm (14 por folha)", "largura": 101.6, "altura": 33.867,
             "colunas": 2, "linhas": 7, "margem_esq": 3.96875, "margem_topo": 21.167, "gap_h": 4.7625, "gap_v": 0},
    "6083": {"nome": "Pimaco 6083 — 101,6 × 50,8 mm (10 por folha)", "largura": 101.6, "altura": 50.8,
             "colunas": 2, "linhas": 5, "margem_esq": 3.96875, "margem_topo": 12.7, "gap_h": 4.7625, "gap_v": 0},
    "6087": {"nome": "Pimaco 6087 — 44,45 × 12,7 mm (80 por folha, só preço + código)", "largura": 44.45, "altura": 12.7,
             "colunas": 4, "linhas": 20, "margem_esq": 7.62, "margem_topo": 12.7, "gap_h": 7.62, "gap_v": 0},
}


def digito_ean13(doze: str) -> str:
    soma = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(doze))
    return str((10 - soma % 10) % 10)


def ean13_valido(codigo: str) -> bool:
    return len(codigo) == 13 and codigo.isdigit() and digito_ean13(codigo[:12]) == codigo[12]


@transaction.atomic
def garantir_codigo(insumo: Insumo) -> str:
    """Gera e grava um EAN-13 interno (2 + sequência) pra produto sem código."""
    if insumo.codigo_barras:
        return insumo.codigo_barras
    internos = [c for c in Insumo.objects.filter(codigo_barras__startswith="2").values_list("codigo_barras", flat=True)
                if c and len(c) == 13 and c.isdigit()]
    seq = max((int(c[1:12]) for c in internos), default=0) + 1
    while True:
        doze = f"2{seq:011d}"
        codigo = doze + digito_ean13(doze)
        if not Insumo.objects.filter(codigo_barras=codigo).exists():
            break
        seq += 1
    Insumo.objects.filter(pk=insumo.pk).update(codigo_barras=codigo)
    insumo.codigo_barras = codigo
    return codigo


def _preco(insumo: Insumo) -> str:
    return f"R$ {insumo.valor:.2f}".replace(".", ",") + (f" / {insumo.unidade_rotulo}" if insumo.unidade != "un" else "")


def gerar_pdf(pedidos: list[tuple[Insumo, int]], modelo: str = "6080", pular: int = 0) -> bytes:
    """`pedidos` = [(insumo, quantidade de etiquetas)]. `pular` = etiquetas já
    usadas no começo da folha (pra reaproveitar folha pela metade)."""
    m = MODELOS.get(modelo) or MODELOS["6080"]
    buffer = BytesIO()
    c = rl_canvas.Canvas(buffer, pagesize=letter)
    largura_pag, altura_pag = letter
    por_folha = m["colunas"] * m["linhas"]
    w, h = m["largura"] * mm, m["altura"] * mm
    pequena = m["altura"] < 15

    etiquetas = [ins for ins, qtd in pedidos for _ in range(max(0, int(qtd)))]
    posicao = max(0, min(int(pular), por_folha - 1))
    for insumo in etiquetas:
        if posicao and posicao % por_folha == 0:
            c.showPage()
        idx = posicao % por_folha
        col, lin = idx % m["colunas"], idx // m["colunas"]
        x = m["margem_esq"] * mm + col * (w + m["gap_h"] * mm)
        y = altura_pag - m["margem_topo"] * mm - (lin + 1) * h - lin * m["gap_v"] * mm
        _desenhar(c, insumo, x, y, w, h, pequena)
        posicao += 1
    if not etiquetas:
        c.setFont("Helvetica", 10)
        c.drawString(20 * mm, altura_pag - 30 * mm, "Nenhuma etiqueta selecionada.")
    c.showPage()
    c.save()
    return buffer.getvalue()


def _desenhar(c, insumo: Insumo, x, y, w, h, pequena: bool):
    codigo = insumo.codigo_barras or ""
    pad = 1.5 * mm
    if pequena:
        # 12,7 mm de altura: preço em cima, código embaixo.
        c.setFont("Helvetica-Bold", 7)
        c.drawString(x + pad, y + h - 3 * mm, _preco(insumo)[:28])
        if codigo:
            _codigo(c, codigo, x + pad, y + 1 * mm, w - 2 * pad, h - 4.8 * mm, legenda=False)
        return
    c.setFont("Helvetica-Bold", 8.5)
    nome = insumo.nome
    while nome and c.stringWidth(nome, "Helvetica-Bold", 8.5) > w - 2 * pad:
        nome = nome[:-2] + "…"
    c.drawString(x + pad, y + h - 3.8 * mm, nome)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x + pad, y + h - 8 * mm, _preco(insumo))
    if codigo:
        _codigo(c, codigo, x + pad, y + 1.2 * mm, w - 2 * pad, h - 10.5 * mm, legenda=True)


def _codigo(c, codigo: str, x, y, largura, altura, legenda: bool):
    tipo = "EAN13" if ean13_valido(codigo) else "Code128"
    valor = codigo[:12] if tipo == "EAN13" else codigo
    desenho = createBarcodeDrawing(tipo, value=valor, barHeight=max(altura - (3 * mm if legenda else 0), 4 * mm),
                                   humanReadable=legenda, fontSize=6)
    escala = min(1, largura / desenho.width)
    desenho.scale(escala, 1)
    desenho.width *= escala
    renderPDF.draw(desenho, c, x, y)
