"""Geração de PDF dos documentos impressos da clínica (Orçamento, Documentos)
com ReportLab — Python puro, sem dependência de sistema (WeasyPrint exigiria
GTK/Pango, indisponível no plano compartilhado da KingHost).

Toda página leva: cabeçalho com logo + dados da clínica, marca d'água
central bem clara (imagem da ConfiguracaoClinica ou, sem ela, o nome da
clínica na diagonal) e rodapé com a numeração."""
from io import BytesIO

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import SimpleDocTemplate

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]


def data_por_extenso(d) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def brl(valor) -> str:
    """12345.6 → "R$ 12.345,60"."""
    from decimal import Decimal

    texto = f"{Decimal(valor):,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


OPACIDADE_MARCA = 0.10
MARGEM = 2 * cm
ALTURA_CABECALHO = 2.6 * cm

# ---- Identidade Lume nos PDFs -------------------------------------------
# Cores medidas na identidade visual (mesmas de static/dist/styles.css).
COR_TEXTO = colors.HexColor("#545936")        # verde escuro — texto e títulos
COR_SUAVE = colors.HexColor("#6F7250")        # texto de apoio
COR_LINHA = colors.HexColor("#949C56")        # verde oliva — linhas fortes
COR_LINHA_SUAVE = colors.HexColor("#DCD6AE")  # divisórias de tabela
COR_FUNDO = colors.HexColor("#F5EFCB")        # marfim — caixas de aviso/cabeçalho de tabela
COR_ALERTA = colors.HexColor("#A9442B")


def _registrar_fontes() -> tuple[str, str, str]:
    """Livvic (textos, OFL, em static/fonts) e Roca Two (títulos — fonte paga
    da marca; só entra se os .ttf licenciados forem colocados em static/fonts).
    Sem os arquivos, cai na Helvetica embutida do PDF."""
    from pathlib import Path

    from django.conf import settings
    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    pasta = Path(settings.BASE_DIR) / "static" / "fonts"
    texto, negrito, titulo = "Helvetica", "Helvetica-Bold", "Helvetica-Bold"
    try:
        if (pasta / "Livvic-Regular.ttf").exists() and (pasta / "Livvic-SemiBold.ttf").exists():
            pdfmetrics.registerFont(TTFont("Livvic", str(pasta / "Livvic-Regular.ttf")))
            pdfmetrics.registerFont(TTFont("Livvic-SemiBold", str(pasta / "Livvic-SemiBold.ttf")))
            addMapping("Livvic", 0, 0, "Livvic"); addMapping("Livvic", 1, 0, "Livvic-SemiBold")
            addMapping("Livvic", 0, 1, "Livvic"); addMapping("Livvic", 1, 1, "Livvic-SemiBold")
            texto, negrito, titulo = "Livvic", "Livvic-SemiBold", "Livvic-SemiBold"
        roca = next((p for p in (pasta / "RocaTwo-Bold.ttf", pasta / "RocaTwo-Regular.ttf") if p.exists()), None)
        if roca:
            pdfmetrics.registerFont(TTFont("RocaTwo", str(roca)))
            titulo = "RocaTwo"
    except Exception:  # fonte corrompida não pode derrubar a emissão do documento
        texto, negrito, titulo = "Helvetica", "Helvetica-Bold", "Helvetica-Bold"
    return texto, negrito, titulo


FONTE_TEXTO, FONTE_NEGRITO, FONTE_TITULO = _registrar_fontes()

_base = getSampleStyleSheet()
ESTILOS = {
    "titulo": ParagraphStyle("titulo", parent=_base["Title"], fontName=FONTE_TITULO, fontSize=17, leading=21,
                             spaceAfter=10, textColor=COR_TEXTO),
    "normal": ParagraphStyle("normal", parent=_base["Normal"], fontName=FONTE_TEXTO, fontSize=10, leading=14, textColor=COR_TEXTO),
    "corpo": ParagraphStyle("corpo", parent=_base["Normal"], fontName=FONTE_TEXTO, fontSize=11, leading=16,
                            alignment=TA_JUSTIFY, spaceAfter=8, textColor=COR_TEXTO),
    "pequeno": ParagraphStyle("pequeno", parent=_base["Normal"], fontName=FONTE_TEXTO, fontSize=8.5, leading=11, textColor=COR_SUAVE),
    "aviso": ParagraphStyle(
        "aviso", parent=_base["Normal"], fontName=FONTE_TEXTO, fontSize=9.5, leading=13, textColor=COR_TEXTO,
        borderColor=COR_LINHA, borderWidth=0.6, borderPadding=8, backColor=COR_FUNDO, spaceBefore=14,
    ),
}


def _imagem_clareada(caminho: str) -> ImageReader | None:
    """Mistura a imagem com branco (mantendo a transparência) pra virar
    marca d'água — mais confiável que alpha do ReportLab em qualquer leitor."""
    try:
        img = Image.open(caminho).convert("RGBA")
    except (OSError, ValueError):
        return None
    branco = Image.new("RGBA", img.size, (255, 255, 255, 255))
    clareada = Image.blend(branco, img, OPACIDADE_MARCA)
    clareada.putalpha(img.getchannel("A"))
    buffer = BytesIO()
    clareada.save(buffer, format="PNG")
    buffer.seek(0)
    return ImageReader(buffer)


def _imagem(caminho: str) -> ImageReader | None:
    try:
        return ImageReader(caminho)
    except (OSError, ValueError):
        return None


def bloco_assinatura(*, nome: str, crmv: str, caminho_assinatura: str | None = None, espaco_antes=1.2 * cm,
                     altura_assinatura=1.6 * cm) -> list:
    """Assinatura centralizada: imagem da assinatura/carimbo (se houver)
    sobre a linha, e embaixo nome completo + CRMV."""
    from reportlab.platypus import Image as RLImage, KeepTogether, Paragraph, Spacer, Table, TableStyle

    celula_imagem = Spacer(1, altura_assinatura)  # espaço pra assinar à mão, se não houver imagem
    if caminho_assinatura:
        try:
            largura_img, altura_img = ImageReader(caminho_assinatura).getSize()
            largura = min(7 * cm, 1.8 * cm * largura_img / altura_img)
            celula_imagem = RLImage(caminho_assinatura, width=largura, height=largura * altura_img / largura_img)
        except (OSError, ValueError, ZeroDivisionError):
            pass
    celulas = [[celula_imagem]]
    estilo_centro = ParagraphStyle("assinatura", parent=ESTILOS["normal"], alignment=1)
    celulas.append([Paragraph(f"<b>{_esc(nome) or 'Médico(a) Veterinário(a)'}</b>", estilo_centro)])
    celulas.append([Paragraph(_esc(crmv) or "CRMV ____________", estilo_centro)])
    celulas.append([Paragraph("Médico(a) Veterinário(a)", ParagraphStyle("assinatura_cargo", parent=ESTILOS["pequeno"], alignment=1))])
    tabela = Table(celulas, colWidths=[8 * cm], hAlign="CENTER")
    tabela.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, 0), "BOTTOM"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, COR_TEXTO),
        ("TOPPADDING", (0, 1), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return [Spacer(1, espaco_antes), KeepTogether([tabela])]


def assinatura_do_usuario(usuario_id, *, nome: str, crmv: str, espaco_antes=1.2 * cm, com_imagem: bool = True,
                          altura_assinatura=1.6 * cm) -> list:
    """Bloco de assinatura com nome/CRMV do snapshot do documento e a imagem
    atual do PerfilProfissional da pessoa (se ela tiver enviado). `com_imagem=False`
    deixa só a linha em branco pra assinar à mão (obrigatório na receita controlada)."""
    from .models import PerfilProfissional

    perfil = PerfilProfissional.objects.filter(usuario_id=usuario_id).first() if usuario_id and com_imagem else None
    caminho = perfil.assinatura.path if perfil and perfil.assinatura else None
    return bloco_assinatura(nome=nome, crmv=crmv, caminho_assinatura=caminho, espaco_antes=espaco_antes,
                            altura_assinatura=altura_assinatura)


def _esc(texto: str) -> str:
    """Escapa pra Paragraph e tira o que a fonte do PDF (Helvetica/WinAnsi)
    não desenha — emojis viravam um quadrado preto."""
    from xml.sax.saxutils import escape

    sem_emoji = (texto or "").encode("cp1252", errors="ignore").decode("cp1252")
    # "🌙 Plantão" vira " Plantão" — tira só o espaço que sobrou do emoji.
    return escape(sem_emoji.lstrip() if sem_emoji != (texto or "") else sem_emoji)


def paragrafos(texto: str, estilo=None) -> list:
    """Texto livre (com quebras de linha) → Paragraphs, escapando HTML."""
    from reportlab.platypus import Paragraph, Spacer

    estilo = estilo or ESTILOS["corpo"]
    saida = []
    for bloco in (texto or "").replace("\r\n", "\n").split("\n\n"):
        if bloco.strip():
            saida.append(Paragraph(_esc(bloco.strip()).replace("\n", "<br/>"), estilo))
        else:
            saida.append(Spacer(1, 0.3 * cm))
    return saida


def _canvas_com_total(desenhar_paginacao):
    """Canvas que só desenha a paginação no fim, quando já sabe o total de
    páginas ("Pág. 1 / 2"). Receita clássica do ReportLab."""

    class CanvasComTotal(Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._paginas = []

        def showPage(self):
            self._paginas.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._paginas)
            for estado in self._paginas:
                self.__dict__.update(estado)
                desenhar_paginacao(self, total)
                super().showPage()
            super().save()

    return CanvasComTotal


def gerar_pdf(*, titulo_documento: str, clinica_nome: str, config, flowables: list, estilo: str = "padrao",
              impresso_por: str = "", rodape=None) -> bytes:
    """`config` = apps.core.models.ConfiguracaoClinica; `flowables` = corpo
    do documento (Paragraph/Table/Spacer do ReportLab).

    `estilo`:
      - "padrao": cabeçalho com linha embaixo, marca d'água, rodapé com o título
        do documento e "Página N".
      - "receita" (layout do receituário): cabeçalho emoldurado, sem marca
        d'água, rodapé "Impresso em: <data hora>  Por: <quem imprimiu>  Pág. x / N"
        (o PDF é gerado a cada abertura/impressão, então é a hora da impressão).
    `rodape` = flowable desenhado FIXO no pé de toda página (a margem de baixo
    cresce pra ele) — ex.: quadro da farmácia na receita controlada."""
    from django.utils import timezone

    receita = estilo == "receita"
    impresso_em = timezone.localtime().strftime("%d/%m/%Y %H:%M")
    caminho_logo = config.marca_dagua.path if config.marca_dagua else None
    logo = _imagem(caminho_logo) if caminho_logo else None
    marca = _imagem_clareada(caminho_logo) if caminho_logo and not receita else None
    contato = " · ".join(filter(None, [config.telefone, config.email]))
    largura, altura = A4
    altura_rodape = rodape.wrap(largura - 2 * MARGEM, altura)[1] if rodape is not None else 0

    def decorar_pagina(canvas, doc):
        canvas.saveState()
        # Marca d'água — desenhada primeiro, fica por baixo do conteúdo (não vai na receita).
        if marca:
            lado = largura * 0.6
            canvas.drawImage(marca, (largura - lado) / 2, (altura - lado) / 2, lado, lado,
                             mask="auto", preserveAspectRatio=True, anchor="c")
        elif not receita:
            canvas.setFillColor(COR_LINHA, alpha=OPACIDADE_MARCA + 0.04)
            canvas.setFont(FONTE_TITULO, 48)
            canvas.translate(largura / 2, altura / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, clinica_nome[:28])
            canvas.rotate(-35)
            canvas.translate(-largura / 2, -altura / 2)

        topo = altura - MARGEM + 0.6 * cm
        recuo = 0.3 * cm if receita else 0  # texto/logo afastados da moldura
        x_texto = MARGEM + recuo
        if logo:
            # Logo da clínica no canto superior DIREITO, em todo documento emitido.
            canvas.drawImage(logo, largura - MARGEM - recuo - 1.8 * cm, topo - 1.9 * cm, 1.8 * cm, 1.8 * cm,
                             mask="auto", preserveAspectRatio=True, anchor="ne")
        # Texto do cabeçalho à esquerda, sem invadir o espaço do logo à direita.
        largura_texto = largura - 2 * MARGEM - 2 * recuo - (2.2 * cm if logo else 0)

        def caber(texto, fonte, tamanho):
            while texto and canvas.stringWidth(texto, fonte, tamanho) > largura_texto:
                texto = texto[:-2] + "…"
            return texto

        canvas.setFillColor(COR_TEXTO)
        canvas.setFont(FONTE_TITULO, 14)
        canvas.drawString(x_texto, topo - 0.5 * cm, caber(clinica_nome, FONTE_TITULO, 14))
        canvas.setFont(FONTE_TEXTO, 8.5)
        identificacao = " · ".join(filter(None, [config.razao_social, f"CNPJ {config.cnpj}" if config.cnpj else ""]))
        linhas = [linha for linha in (identificacao, config.endereco_completo, contato) if linha]
        for i, linha in enumerate(linhas[:3]):
            canvas.drawString(x_texto, topo - (0.95 + 0.4 * i) * cm, caber(linha, FONTE_TEXTO, 8.5))
        canvas.setStrokeColor(COR_LINHA)
        if receita:
            canvas.setLineWidth(0.8)
            canvas.rect(MARGEM, topo - 2.15 * cm, largura - 2 * MARGEM, 2.45 * cm)
        else:
            canvas.setLineWidth(1.2)
            canvas.line(MARGEM, topo - 2.0 * cm, largura - MARGEM, topo - 2.0 * cm)

        canvas.setFont(FONTE_TEXTO, 8)
        canvas.setFillColor(COR_SUAVE)
        if receita:
            canvas.drawString(MARGEM, 1.2 * cm, f"Impresso em: {impresso_em}")
            if impresso_por:
                canvas.drawCentredString(largura / 2, 1.2 * cm, f"Por: {impresso_por}")
            # "Pág. x / N" é desenhado no fim, pelo CanvasComTotal.
        else:
            canvas.drawString(MARGEM, 1.2 * cm, titulo_documento)
            canvas.drawRightString(largura - MARGEM, 1.2 * cm, f"Página {doc.page}")
        if rodape is not None:
            rodape.drawOn(canvas, MARGEM, 1.7 * cm)
        canvas.restoreState()

    def paginacao(canvas, total):
        canvas.saveState()
        canvas.setFont(FONTE_TEXTO, 8)
        canvas.setFillColor(COR_SUAVE)
        canvas.drawRightString(largura - MARGEM, 1.2 * cm, f"Pág. {canvas.getPageNumber()} / {total}")
        canvas.restoreState()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, title=titulo_documento, author=clinica_nome,
        leftMargin=MARGEM, rightMargin=MARGEM, topMargin=MARGEM + ALTURA_CABECALHO - 0.6 * cm,
        bottomMargin=2 * cm + (altura_rodape + 0.2 * cm if altura_rodape else 0),
    )
    extras = {"canvasmaker": _canvas_com_total(paginacao)} if receita else {}
    doc.build(flowables, onFirstPage=decorar_pagina, onLaterPages=decorar_pagina, **extras)
    return buffer.getvalue()
