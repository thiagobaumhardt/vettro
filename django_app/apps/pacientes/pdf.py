"""PDF de um registro da Ficha (Atendimento/Consulta/Cirurgia) — botão Imprimir do
detalhe aberto pelo histórico. Usa o mesmo contexto da tela (views._contexto_registro),
então o impresso mostra exatamente o que a tela mostra."""
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

from apps.core.models import ConfiguracaoClinica
from apps.core.pdf import COR_FUNDO, COR_LINHA, COR_LINHA_SUAVE, ESTILOS, _esc, gerar_pdf

LARGURA_UTIL = 17 * cm - 12  # A4 com margens de 2 cm, menos o padding interno do frame (6 pt de cada lado)


def _estilos():
    e = ESTILOS
    return {
        "texto": ParagraphStyle("reg_texto", parent=e["normal"], fontSize=10, leading=13.5),
        "secao": ParagraphStyle("reg_secao", parent=e["normal"], fontSize=10.5, leading=14, spaceBefore=8, spaceAfter=4),
        "titulo": ParagraphStyle("reg_titulo", parent=e["normal"], fontName=e["titulo"].fontName, fontSize=13,
                                 leading=17, alignment=1),
        "celula": ParagraphStyle("reg_celula", parent=e["normal"], fontSize=9, leading=11.5),
        "direita": ParagraphStyle("reg_direita", parent=e["normal"], fontSize=9, leading=11.5, alignment=2),
    }


def _secao(titulo, estilos):
    return Paragraph(f"<u><b>{_esc(titulo)}:</b></u>", estilos["secao"])


def _campos(campos, estilos) -> list:
    """Campos curtos em 2 colunas; campos de texto longo ocupam a linha toda."""
    saida, pares = [], []

    def descarregar():
        if not pares:
            return
        linhas = [pares[i:i + 2] + [""] * (2 - len(pares[i:i + 2])) for i in range(0, len(pares), 2)]
        t = Table(linhas, colWidths=[LARGURA_UTIL / 2] * 2)
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]))
        saida.append(t)
        pares.clear()

    for rotulo, valor, largo in campos:
        texto = _esc(str(valor)).replace("\n", "<br/>")
        p = Paragraph(f"<b>{_esc(rotulo)}</b>: {texto}", estilos["texto"])
        if largo:
            descarregar()
            saida.append(p)
        else:
            pares.append(p)
    descarregar()
    return saida


def _itens(contexto, estilos) -> list:
    servicos, insumos = contexto["registro_servicos"], contexto["registro_insumos"]
    tipo_servico = "Procedimento" if contexto["registro_tipo"] == "cirurgia" else "Serviço"
    c, d = estilos["celula"], estilos["direita"]
    linhas = [[Paragraph(f"<b>{t}</b>", d if i >= 2 else c) for i, t in enumerate(["Item", "Tipo", "Qtd.", "Valor unit.", "Subtotal"])]]
    for item in servicos:
        qtd = item.get("qtd") or "1"
        unidade = item.get("unidade") if item.get("unidade") not in ("", None, "un.") else ""
        linhas.append([Paragraph(_esc(item["nome"]), c), Paragraph(tipo_servico, c),
                       Paragraph(_esc(f"{qtd} {unidade}".strip()), d), Paragraph(f"R$ {item['valor']}", d),
                       Paragraph(f"R$ {item.get('subtotal') or item['valor']}", d)])
    for item in insumos:
        linhas.append([Paragraph(_esc(item["nome"]), c), Paragraph("Insumo", c),
                       Paragraph(_esc(f"{item.get('qtd', '')} {item.get('unidade', '')}".strip()), d),
                       Paragraph(f"R$ {item['valor']}", d), Paragraph(f"R$ {item['subtotal']}" if item.get("subtotal") else "—", d)])
    total = contexto["registro"].total
    linhas.append(["", "", "", Paragraph("<b>Total</b>", d), Paragraph(f"<b>R$ {total}</b>", d)])
    t = Table(linhas, colWidths=[6.2 * cm, 2.5 * cm, 2.3 * cm, 2.5 * cm, 2.65 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COR_FUNDO),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, COR_LINHA),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, COR_LINHA_SUAVE),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, COR_LINHA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    if not servicos and not insumos:
        return [Paragraph("Nenhum serviço ou insumo cobrado.", estilos["texto"]),
                Paragraph(f"<b>Total</b>: R$ {total}", estilos["texto"])]
    return [t]


def pdf_registro(contexto: dict, *, clinica_nome: str, impresso_por: str = "") -> bytes:
    estilos = _estilos()
    paciente, registro = contexto["paciente"], contexto["registro"]
    tutor = paciente.tutor

    caixa = Table([[Paragraph(f"<b>{_esc(contexto['registro_titulo'])}</b>", estilos["titulo"])]], colWidths=[LARGURA_UTIL])
    caixa.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, COR_LINHA),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    corpo = [caixa, Spacer(1, 0.15 * cm)]

    corpo.append(_secao("Paciente", estilos))
    corpo += _campos([
        ("Nome do animal", paciente.nome, False), ("Espécie", paciente.get_especie_display(), False),
        ("Raça", paciente.raca or "—", False), ("Tutor", tutor.nome if tutor else "—", False),
    ], estilos)

    for titulo, campos in contexto["registro_secoes"]:
        corpo.append(_secao(titulo, estilos))
        corpo += _campos(campos, estilos)

    corpo.append(_secao("Itens cobrados", estilos))
    corpo += _itens(contexto, estilos)

    if contexto["registro_tipo"] == "atendimento":
        anexos = [f"Exame: {e.nome}" for e in contexto["registro_exames"]] + [
            f"Foto: {f.nome or 'sem nome'}" for f in contexto["registro_fotos"]]
        corpo.append(_secao("Exames e fotos vinculados", estilos))
        corpo.append(Paragraph("<br/>".join(_esc(a) for a in anexos) if anexos else "Nenhum.", estilos["texto"]))

    return gerar_pdf(
        titulo_documento=f"{contexto['registro_titulo']} · {paciente.nome}", clinica_nome=clinica_nome,
        config=ConfiguracaoClinica.atual(), flowables=[KeepTogether(corpo[:2])] + corpo[2:],
        estilo="receita", impresso_por=impresso_por,
    )


def pdf_historico(paciente, eventos: list[dict], *, filtro_rotulo: str = "", clinica_nome: str,
                  impresso_por: str = "") -> bytes:
    """Histórico de atendimentos do paciente (aba Histórico), já filtrado pela categoria escolhida."""
    estilos = _estilos()
    tutor = paciente.tutor
    titulo = "Histórico de atendimentos" + (f" — {filtro_rotulo}" if filtro_rotulo else "")
    caixa = Table([[Paragraph(f"<b>{_esc(titulo)}</b>", estilos["titulo"])]], colWidths=[LARGURA_UTIL])
    caixa.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, COR_LINHA),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    corpo = [caixa, Spacer(1, 0.15 * cm), _secao("Paciente", estilos)]
    corpo += _campos([
        ("Nome do animal", paciente.nome, False), ("Espécie", paciente.get_especie_display(), False),
        ("Raça", paciente.raca or "—", False), ("Tutor", tutor.nome if tutor else "—", False),
    ], estilos)
    corpo.append(_secao(f"Registros ({len(eventos)})", estilos))

    if not eventos:
        corpo.append(Paragraph("Nenhum registro.", estilos["texto"]))
    else:
        c, d = estilos["celula"], estilos["direita"]
        linhas = [[Paragraph("<b>Data</b>", c), Paragraph("<b>Registro</b>", c), Paragraph("<b>Detalhes</b>", c),
                   Paragraph("<b>Total</b>", d)]]
        for e in eventos:
            detalhe = " — ".join(filter(None, [e.get("detalhe") or "", e.get("obs") or ""]))
            if len(detalhe) > 400:
                detalhe = detalhe[:400] + "…"
            quando = e["data"].strftime("%d/%m/%Y") + (f" {e['hora']:%H:%M}" if e.get("hora") else "")
            linhas.append([
                Paragraph(quando, c),
                Paragraph(_esc(e["titulo"]) + (" <font size='8'>(plantão)</font>" if e.get("plantao") else ""), c),
                Paragraph(_esc(detalhe).replace("\n", "<br/>"), c),
                Paragraph(f"R$ {e['total']}" if e.get("total") is not None else "—", d),
            ])
        t = Table(linhas, colWidths=[2.4 * cm, 4.0 * cm, 7.8 * cm, 1.95 * cm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COR_FUNDO),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, COR_LINHA),
            ("LINEBELOW", (0, 1), (-1, -1), 0.4, COR_LINHA_SUAVE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        corpo.append(t)

    return gerar_pdf(
        titulo_documento=f"{titulo} · {paciente.nome}", clinica_nome=clinica_nome,
        config=ConfiguracaoClinica.atual(), flowables=corpo, estilo="receita", impresso_por=impresso_por,
    )
