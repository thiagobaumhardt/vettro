from django.utils import timezone
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, Spacer, Table, TableStyle

from apps.core.models import ConfiguracaoClinica, PerfilProfissional
from apps.core.pdf import COR_LINHA, COR_TEXTO as COR_TEXTO_LINHA, ESTILOS, _esc, assinatura_do_usuario, gerar_pdf, paragrafos

from .models import FARMACIA_CHOICES, USO_CHOICES, Receita

CAMPOS_ITEM = ("uso", "medicamento", "farmacia", "concentracao", "quantidade", "periodicidade", "tempo_uso", "obs")
MAX_ITENS = 30


class ReceitaInvalidaError(Exception):
    pass


def itens_do_post(post) -> list[dict]:
    """Linhas paralelas `item_<campo>` do formulário; ignora as totalmente vazias."""
    colunas = [post.getlist(f"item_{campo}") for campo in CAMPOS_ITEM]
    usos, farmacias = dict(USO_CHOICES), dict(FARMACIA_CHOICES)
    itens = []
    for valores in zip(*colunas):
        item = {campo: valor.strip()[:300] for campo, valor in zip(CAMPOS_ITEM, valores)}
        if not any(item[c] for c in ("medicamento", "concentracao", "quantidade", "periodicidade", "tempo_uso", "obs")):
            continue
        if not item["medicamento"]:
            raise ReceitaInvalidaError("Todo medicamento precisa de um nome.")
        if not item["quantidade"]:
            raise ReceitaInvalidaError(f"Informe a quantidade de “{item['medicamento']}”.")
        if item["uso"] not in usos:
            raise ReceitaInvalidaError(f"Escolha o uso de “{item['medicamento']}”.")
        if item["farmacia"] and item["farmacia"] not in farmacias:
            raise ReceitaInvalidaError(f"Farmácia inválida em “{item['medicamento']}”.")
        itens.append(item)
    if not itens:
        raise ReceitaInvalidaError("Adicione ao menos um medicamento.")
    if len(itens) > MAX_ITENS:
        raise ReceitaInvalidaError(f"Máximo de {MAX_ITENS} medicamentos por receita.")
    return itens


def criar_receita(*, paciente, tipo, texto, itens, usuario) -> Receita:
    perfil = PerfilProfissional.de(usuario)
    tutor = paciente.tutor
    return Receita.objects.create(
        paciente=paciente, tipo=tipo, texto=texto if tipo == Receita.Tipo.LIVRE else "",
        itens=itens if tipo != Receita.Tipo.LIVRE else [],
        pac_nome=paciente.nome, pac_especie=paciente.get_especie_display(), pac_raca=paciente.raca,
        pac_idade=paciente.idade_texto if paciente.data_nascimento else "",
        pac_peso=f"{paciente.peso} kg" if paciente.peso else "",
        tutor_nome=tutor.nome if tutor else "", tutor_endereco=_logradouro(tutor) if tutor else "",
        tutor_cidade_uf=", ".join(filter(None, [tutor.cidade, tutor.uf.upper()])) if tutor else "",
        tutor_cpf=tutor.cpf if tutor else "", tutor_rg=tutor.rg if tutor else "",
        pac_sexo=paciente.get_sexo_display(),
        vet_usuario_id=usuario.id, vet_nome=perfil.nome_completo or usuario.nome, vet_crmv=perfil.crmv_formatado,
        vet_mapa=perfil.mapa,
    )



def _logradouro(origem) -> str:
    """Rua, nº - complemento - bairro (Tutor ou PerfilProfissional/ConfiguracaoClinica)."""
    rua = ", ".join(filter(None, [origem.endereco, origem.numero]))
    return " - ".join(p for p in [rua, origem.complemento, origem.bairro] if p)


def _cidade_uf(origem) -> str:
    return ", ".join(filter(None, [origem.cidade, (origem.uf or "").upper()]))


# --- Layout do receituário (modelo enviado pela clínica, 2026-10) -------------------

def _estilos_receita():
    e = ESTILOS
    return {
        "texto": ParagraphStyle("rec_texto", parent=e["normal"], fontSize=10, leading=13),
        "secao": ParagraphStyle("rec_secao", parent=e["normal"], fontSize=10.5, leading=14, spaceBefore=6, spaceAfter=3),
        "titulo": ParagraphStyle("rec_titulo", parent=e["normal"], fontName=e["titulo"].fontName, fontSize=13,
                                 leading=17, alignment=1),
        "item": ParagraphStyle("rec_item", parent=e["normal"], fontSize=10.5, leading=14, spaceBefore=4, spaceAfter=2),
        "via": ParagraphStyle("rec_via", parent=e["normal"], fontSize=9, alignment=2),
    }


def _campo(rotulo: str, valor) -> str:
    return f"<b>{_esc(rotulo)}</b>: {_esc(valor or '')}"


def _linha(*campos: str) -> str:
    return "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;".join(campos)


def _caixa_titulo(texto: str, estilos):
    t = Table([[Paragraph(f"<b>{_esc(texto)}</b>", estilos["titulo"])]], colWidths=[LARGURA_UTIL])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, COR_LINHA),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _bloco(titulo: str, linhas: list[str], estilos) -> list:
    """Título sublinhado ("Dados do emitente:") + linhas "Rótulo: valor"."""
    return [Paragraph(f"<u><b>{_esc(titulo)}:</b></u>", estilos["secao"])] + [
        Paragraph(linha, estilos["texto"]) for linha in linhas
    ]


def _dados_emitente(receita: Receita) -> list[str]:
    """Endereço/telefone do perfil do(a) veterinário(a); vazio cai no da clínica."""
    config = ConfiguracaoClinica.atual()
    perfil = PerfilProfissional.objects.filter(usuario_id=receita.vet_usuario_id).first() if receita.vet_usuario_id else None
    origem = perfil if perfil and perfil.endereco else config
    telefones = " - ".join(dict.fromkeys(t for t in [perfil.telefone if perfil else "", config.telefone] if t))
    return [
        _linha(_campo("Nome", receita.vet_nome), _campo("CRMV", receita.vet_crmv), _campo("MAPA", receita.vet_mapa)),
        _campo("Endereço", _logradouro(origem)),
        _campo("Cidade / Estado", _cidade_uf(origem)),
        _campo("Telefones", telefones),
        _campo("Data de emissão", timezone.localtime(receita.criado_em).strftime("%d/%m/%Y")),
    ]


def _dados_tutor(receita: Receita) -> list[str]:
    return [
        _campo("Nome do tutor", receita.tutor_nome),
        _linha(_campo("CPF", receita.tutor_cpf), _campo("RG", receita.tutor_rg)),
        _campo("Endereço", receita.tutor_endereco),
        _campo("Cidade / Estado", receita.tutor_cidade_uf),
    ]


def _dados_animal(receita: Receita) -> list[str]:
    return [
        _campo("Nome do animal", receita.pac_nome),
        _linha(_campo("Espécie", receita.pac_especie), _campo("Raça", receita.pac_raca)),
        _linha(_campo("Sexo", receita.pac_sexo), _campo("Idade", receita.pac_idade), _campo("Peso", receita.pac_peso)),
    ]


def _prescricao(receita: Receita, estilos) -> list:
    corpo = [Paragraph("<u><b>Prescrição:</b></u>", estilos["secao"])]
    if receita.tipo == Receita.Tipo.LIVRE:
        return corpo + paragrafos(receita.texto)
    farmacias = dict(FARMACIA_CHOICES)
    numero = 0
    for codigo_uso, rotulo_uso in USO_CHOICES:  # agrupa na ordem fixa dos usos
        do_uso = [i for i in receita.itens if i["uso"] == codigo_uso]
        if not do_uso:
            continue
        corpo.append(Paragraph(_esc(rotulo_uso.upper()), estilos["texto"]))
        for item in do_uso:
            numero += 1
            titulo = f"{numero}) {_esc(item['medicamento'])}" + (f" {_esc(item['concentracao'])}" if item["concentracao"] else "")
            if item["farmacia"]:
                titulo += f" ---- {_esc(farmacias[item['farmacia']].lower())}"
            bloco = [Paragraph(f"<b>{titulo}</b>", estilos["item"])]
            posologia = ". ".join(filter(None, [
                # Receitas antigas (antes de 2026-10) não têm quantidade.
                f"Quantidade: {_esc(item['quantidade'])}" if item.get("quantidade") else "",
                f"Periodicidade: {_esc(item['periodicidade'])}" if item["periodicidade"] else "",
                f"Período de uso: {_esc(item['tempo_uso'])}" if item["tempo_uso"] else "",
            ]))
            if posologia:
                bloco.append(Paragraph(posologia + ".", estilos["texto"]))
            if item["obs"]:
                bloco.append(Paragraph(_esc(item["obs"]), estilos["texto"]))
            corpo.append(KeepTogether(bloco))
    return corpo


def _marcar_farmacia(receita: Receita) -> str:
    """ "Farmácia veterinária ( X )   Farmácia Humana (  )" conforme os itens."""
    tipos = {i.get("farmacia") for i in receita.itens}
    marca = lambda chave: "X" if chave in tipos else "&nbsp;&nbsp;"  # noqa: E731
    return (f"Farmácia veterinária ( {marca('veterinaria')} )&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"Farmácia Humana ( {marca('humana')} )")


# Quadro da farmácia (receita controlada) — largura útil do A4 com margens de 2 cm = 17 cm.
LARGURA_UTIL = 17 * cm


def _quadro_farmacia(receita: Receita):
    """Rodapé da receita controlada, preenchido à mão pela FARMÁCIA: Identificação
    do comprador | Identificação do fornecedor (assinatura do farmacêutico + data),
    com moldura dupla, e a legenda das vias embaixo. Desenhado fixo no pé de cada
    página via gerar_pdf(rodape=...), então nunca empurra a receita pra outra página."""
    estilos = _estilos_receita()
    texto = ParagraphStyle("rec_quadro", parent=estilos["texto"], fontSize=9.5, leading=13.5)
    meia = (LARGURA_UTIL - 0.3 * cm) / 2
    comprador = Paragraph(
        "Nome: ______________________________________<br/>"
        "RG: ____________________ Órg. Emissor: _________<br/>"
        "End.: ______________________________________<br/>"
        "Cidade: __________________________ UF: _______<br/>"
        "Telefone: ___________________________________", texto)
    fornecedor = Paragraph(
        "<br/><br/><br/>___________________________________<br/>"
        "Assinatura do Farmacêutico&nbsp;&nbsp;&nbsp;DATA ___/___/_____", texto)
    interno = Table([
        [Paragraph("<b>Identificação do comprador:</b>", texto), Paragraph("<b>Identificação do fornecedor:</b>", texto)],
        [comprador, fornecedor],
    ], colWidths=[meia, meia])
    interno.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, COR_TEXTO_LINHA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    # Moldura dupla: a tabela interna dentro de outra com borda, afastada 2 pt.
    moldura = Table([[interno]], colWidths=[LARGURA_UTIL])
    moldura.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, COR_TEXTO_LINHA),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    legenda = Paragraph("1ª via - Farmácia / 2ª via - Paciente", ParagraphStyle("rec_legenda", parent=texto, fontSize=9))
    # "Farmácia veterinária ( ) Farmácia Humana ( )" colado em cima do quadro do comprador.
    farmacia = Paragraph(_marcar_farmacia(receita), estilos["texto"])
    quadro = Table([[farmacia], [moldura], [legenda]], colWidths=[LARGURA_UTIL])
    quadro.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 3), ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
    ]))
    return quadro


def _corpo_receita(receita: Receita, via: str | None) -> list:
    estilos = _estilos_receita()
    controlada = receita.tipo == Receita.Tipo.CONTROLADA
    corpo = []
    if via:
        corpo.append(Paragraph(f"<b>{via}</b>", estilos["via"]))
        corpo.append(Spacer(1, 0.1 * cm))
    corpo.append(_caixa_titulo("Receituário de Controle Especial" if controlada else "Receituário", estilos))
    corpo.append(Spacer(1, 0.2 * cm))
    # Blocos fixos, nesta ordem: emitente, tutor, animal, prescrição.
    corpo += _bloco("Dados do emitente", _dados_emitente(receita), estilos)
    corpo += _bloco("Dados do tutor", _dados_tutor(receita), estilos)
    corpo += _bloco("Dados do animal", _dados_animal(receita), estilos)
    corpo += _prescricao(receita, estilos)
    # Simples/livre: sai com a assinatura anexada no cadastro do vet. Controlada: NUNCA —
    # o(a) veterinário(a) tem que assinar à mão (pedido da clínica, 2026-10).
    corpo += assinatura_do_usuario(receita.vet_usuario_id, nome=receita.vet_nome, crmv=receita.vet_crmv,
                                   espaco_antes=0.9 * cm, com_imagem=not controlada, altura_assinatura=2.2 * cm)
    return corpo


def pdf_receita(receita: Receita, *, clinica_nome: str, impresso_por: str = "") -> bytes:
    if receita.tipo == Receita.Tipo.CONTROLADA:
        corpo = _corpo_receita(receita, "1ª via — Farmácia") + [PageBreak()] + _corpo_receita(receita, "2ª via — Paciente")
    else:
        corpo = _corpo_receita(receita, None)
    return gerar_pdf(
        titulo_documento=f"{receita.get_tipo_display()} · {receita.pac_nome}", clinica_nome=clinica_nome,
        config=ConfiguracaoClinica.atual(), flowables=corpo, estilo="receita", impresso_por=impresso_por,
        rodape=_quadro_farmacia(receita) if receita.tipo == Receita.Tipo.CONTROLADA else None,
    )
