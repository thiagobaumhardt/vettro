"""Regras de negócio de Estoque — porte de backend/app/utils.py (montar_insumos/
debitar_estoque) reestruturado em torno do ledger SD1/SD2/SD3 (§3/§9 do plano)."""
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Q

from .models import Insumo, MovimentoEstoque
from .nfe import parsear_nfe


def formatar_qtd(valor) -> str:
    """Decimal → texto curto em pt-BR: 100 → "100", 2.500 → "2,5"."""
    texto = f"{Decimal(valor).normalize():f}"
    return texto.replace(".", ",")


def insumos_para_busca(insumos) -> list[dict]:
    """Catálogo pro componente de busca de insumos (components/_insumos_busca.html)."""
    return [
        {"id": str(i.id), "nome": i.nome, "valor": str(i.valor), "unidade": i.unidade_rotulo,
         "estoque": formatar_qtd(i.qtd), "estoque_num": float(i.qtd),
         "codigo_barras": i.codigo_barras or ""}
        for i in insumos
    ]


class EstoqueInsuficienteError(Exception):
    def __init__(self, insumo_nome: str, disponivel, solicitado, unidade: str = ""):
        self.insumo_nome = insumo_nome
        self.disponivel = disponivel
        self.solicitado = solicitado
        sufixo = f" {unidade}" if unidade else ""
        super().__init__(
            f"Estoque insuficiente para {insumo_nome}: disponível {formatar_qtd(disponivel)}{sufixo}, "
            f"solicitado {formatar_qtd(solicitado)}{sufixo}."
        )


def para_unidade_de_uso(insumo: Insumo, quantidade, em_embalagens: bool) -> Decimal:
    """Converte o que foi digitado (embalagens ou unidades) pra unidade de uso."""
    quantidade = Decimal(str(quantidade))
    return quantidade * insumo.unidades_por_pacote if em_embalagens else quantidade


@transaction.atomic
def registrar_movimento(
    *, insumo: Insumo, tipo: str, subtipo: str, quantidade: Decimal,
    valor_unitario: Decimal | None = None, origem_tipo: str = "", origem_id=None,
    nota_fiscal_chave: str = "", nota_fiscal_numero: str = "", observacao: str = "",
    usuario=None,
) -> MovimentoEstoque:
    """Única função autorizada a mudar Insumo.qtd — sempre grava o
    MovimentoEstoque junto, na mesma transação. `select_for_update` evita
    corrida entre débitos concorrentes do mesmo insumo."""
    insumo_travado = Insumo.objects.select_for_update().get(pk=insumo.pk)
    quantidade = Decimal(str(quantidade))
    if quantidade <= 0:
        raise ValueError("Quantidade de movimento deve ser positiva.")

    if tipo == MovimentoEstoque.SD2_SAIDA and insumo_travado.qtd < quantidade:
        raise EstoqueInsuficienteError(insumo_travado.nome, insumo_travado.qtd, quantidade, insumo_travado.unidade_rotulo)

    if tipo == MovimentoEstoque.SD1_ENTRADA:
        delta = quantidade
    elif tipo == MovimentoEstoque.SD2_SAIDA:
        delta = -quantidade
    else:  # SD3 — sinal depende do subtipo
        delta = quantidade if subtipo in MovimentoEstoque.SUBTIPOS_SD3_POSITIVOS else -quantidade

    insumo_travado.qtd = insumo_travado.qtd + delta
    insumo_travado.save(update_fields=["qtd"])

    return MovimentoEstoque.objects.create(
        insumo=insumo_travado, tipo=tipo, subtipo=subtipo, quantidade=quantidade,
        valor_unitario=valor_unitario, origem_tipo=origem_tipo, origem_id=origem_id,
        nota_fiscal_chave=nota_fiscal_chave, nota_fiscal_numero=nota_fiscal_numero,
        observacao=observacao,
        usuario_id=getattr(usuario, "id", None),
        usuario_nome=getattr(usuario, "nome", ""),
    )


def debitar_para_consumo(*, insumo: Insumo, quantidade: int, subtipo: str,
                          origem_tipo: str, origem_id, usuario) -> MovimentoEstoque:
    """SD2 — saída por consumo em anamnese/cirurgia/atendimento/cobrança."""
    return registrar_movimento(
        insumo=insumo, tipo=MovimentoEstoque.SD2_SAIDA, subtipo=subtipo,
        quantidade=quantidade, valor_unitario=insumo.valor,
        origem_tipo=origem_tipo, origem_id=origem_id, usuario=usuario,
    )


@transaction.atomic
def estornar_consumo(*, origem_tipo: str, origem_id, usuario) -> int:
    """SD3 — devolve ao estoque tudo que foi debitado (SD2) por um documento
    de origem, chamado ao excluir esse documento (Atendimento/Anamnese/
    Cirurgia/Cobrança manual). O SD2 original fica no ledger; o estorno é
    um movimento novo que o compensa. Retorna quantos itens foram estornados."""
    saidas = MovimentoEstoque.objects.filter(
        tipo=MovimentoEstoque.SD2_SAIDA, origem_tipo=origem_tipo, origem_id=origem_id,
    ).select_related("insumo")
    total = 0
    for saida in saidas:
        registrar_movimento(
            insumo=saida.insumo, tipo=MovimentoEstoque.SD3_INTERNO, subtipo="estorno_consumo",
            quantidade=saida.quantidade, valor_unitario=saida.valor_unitario,
            origem_tipo=origem_tipo, origem_id=origem_id,
            observacao=f"Estorno por exclusão de {origem_tipo}", usuario=usuario,
        )
        total += 1
    return total


def entrada_manual(*, insumo: Insumo, quantidade: int, valor_unitario: Decimal,
                    usuario, observacao: str = "", lote: str = "", data_validade=None) -> MovimentoEstoque:
    """SD1 — entrada sem nota fiscal (cadastro novo ou reposição de item
    existente), conforme pedido explicitamente pelo usuário."""
    campos_alterados = []
    if lote:
        insumo.lote = lote
        campos_alterados.append("lote")
    if data_validade:
        insumo.data_validade = data_validade
        campos_alterados.append("data_validade")
    if campos_alterados:
        insumo.save(update_fields=campos_alterados)

    return registrar_movimento(
        insumo=insumo, tipo=MovimentoEstoque.SD1_ENTRADA, subtipo="manual_sem_nota",
        quantidade=quantidade, valor_unitario=valor_unitario,
        observacao=observacao or "Entrada manual sem nota fiscal", usuario=usuario,
    )


def ajustar_estoque(*, insumo: Insumo, quantidade: int, positivo: bool, motivo: str, usuario) -> MovimentoEstoque:
    """SD3 — ajuste interno (contagem, perda) com motivo obrigatório."""
    return registrar_movimento(
        insumo=insumo, tipo=MovimentoEstoque.SD3_INTERNO,
        subtipo="ajuste_positivo" if positivo else "ajuste_negativo",
        quantidade=quantidade, observacao=motivo, usuario=usuario,
    )


@transaction.atomic
def importar_nfe(conteudo_xml: bytes, usuario) -> dict:
    """SD1 — entrada via XML de NF-e do fornecedor. Casa por código de
    barras; cria insumo novo se não achar, incrementa se achar. Também
    preenche o NCM automaticamente (vem no XML)."""
    itens = parsear_nfe(conteudo_xml)

    criados = atualizados = ignorados = 0
    revisar = []  # produtos novos vindos em embalagem: conferir o conteúdo
    for item in itens:
        if item["quantidade"] <= 0:
            ignorados += 1
            continue

        valor_embalagem = item["valor_unitario"]
        insumo = Insumo.objects.filter(codigo_barras=item["codigo_barras"]).first() if item["codigo_barras"] else None

        if insumo:
            # A nota vem na unidade comercial do fornecedor (ex.: 2 CX) —
            # converte pra unidade de uso com o conteúdo da embalagem.
            qtd_uso = item["quantidade"] * insumo.unidades_por_pacote
            custo_uso = (valor_embalagem / insumo.unidades_por_pacote).quantize(Decimal("0.0001"))
            campos_alterados = []
            if item["lote"]:
                insumo.lote = item["lote"]
                campos_alterados.append("lote")
            if item["validade"]:
                insumo.data_validade = item["validade"]
                campos_alterados.append("data_validade")
            if item["ncm"] and not insumo.ncm:
                insumo.ncm = item["ncm"]
                campos_alterados.append("ncm")
            # ST e origem seguem sempre a nota mais recente do fornecedor.
            if insumo.tem_st != item["tem_st"]:
                insumo.tem_st = item["tem_st"]
                campos_alterados.append("tem_st")
            if item["origem"] and insumo.origem != item["origem"]:
                insumo.origem = item["origem"]
                campos_alterados.append("origem")
            if campos_alterados:
                insumo.save(update_fields=campos_alterados)

            registrar_movimento(
                insumo=insumo, tipo=MovimentoEstoque.SD1_ENTRADA, subtipo="nfe_fornecedor",
                quantidade=qtd_uso, valor_unitario=custo_uso,
                observacao=(
                    f"+{formatar_qtd(item['quantidade'])} {item['unidade_comercial'] or 'emb.'} "
                    f"= {formatar_qtd(qtd_uso)} {insumo.unidade_rotulo} via XML de NF-e"
                ),
                usuario=usuario,
            )
            atualizados += 1
        else:
            # Produto novo: ainda não sabemos quantas unidades vêm na
            # embalagem — entra 1:1 e fica na lista pra conferir.
            unidade_comercial = (item["unidade_comercial"] or "").strip()
            insumo = Insumo.objects.create(
                nome=item["nome"], valor=valor_embalagem, qtd=0,
                embalagem=unidade_comercial.lower()[:30],
                codigo_barras=item["codigo_barras"], lote=item["lote"] or "",
                data_validade=item["validade"], ncm=item["ncm"] or "",
                tem_st=item["tem_st"], origem=item["origem"] or "0",
                obs="Importado via XML de NF-e.",
            )
            registrar_movimento(
                insumo=insumo, tipo=MovimentoEstoque.SD1_ENTRADA, subtipo="nfe_fornecedor",
                quantidade=item["quantidade"], valor_unitario=valor_embalagem,
                observacao="Criado via XML de NF-e", usuario=usuario,
            )
            if unidade_comercial.upper() not in UNIDADES_COMERCIAIS_AVULSAS:
                revisar.append(insumo)
            criados += 1

    return {"criados": criados, "atualizados": atualizados, "ignorados": ignorados, "revisar": revisar}


# Unidades comerciais da NF-e que já são a unidade de uso (não precisam de
# conversão). Qualquer outra (CX, PCT, FR, KIT...) pede conferência.
UNIDADES_COMERCIAIS_AVULSAS = {"UN", "UND", "UNID", "UNIDADE", "PC", "PCA", "PECA", ""}


def alertas_estoque() -> dict:
    """Porte de dashboard.py:/estoque-alerta — limiar de estoque baixo (<3) e
    janela de validade (60 dias) vêm de settings (constantes do plano, §9)."""
    from datetime import date, timedelta

    from django.conf import settings

    hoje = date.today()
    return {
        # Sem NCM não dá pra emitir NFC-e do produto na venda de balcão.
        "sem_ncm": Insumo.objects.filter(ncm=""),
        "zerados": Insumo.objects.filter(qtd__lte=0),
        # Estoque mínimo do produto; sem ele, a regra geral (< 3 unidades de uso).
        "baixos": Insumo.objects.filter(qtd__gt=0).filter(
            Q(estoque_minimo__isnull=True, qtd__lt=settings.ESTOQUE_BAIXO_LIMIAR) | Q(qtd__lt=F("estoque_minimo"))
        ),
        "vencidos": Insumo.objects.filter(data_validade__lt=hoje),
        "vencendo": Insumo.objects.filter(
            data_validade__gte=hoje,
            data_validade__lte=hoje + timedelta(days=settings.VALIDADE_ALERTA_DIAS),
        ),
    }
