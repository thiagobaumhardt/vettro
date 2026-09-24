"""Regras de negócio de Estoque — porte de backend/app/utils.py (montar_insumos/
debitar_estoque) reestruturado em torno do ledger SD1/SD2/SD3 (§3/§9 do plano)."""
from decimal import Decimal

from django.db import transaction

from .models import Insumo, MovimentoEstoque
from .nfe import parsear_nfe


class EstoqueInsuficienteError(Exception):
    def __init__(self, insumo_nome: str, disponivel: int, solicitado: int):
        self.insumo_nome = insumo_nome
        self.disponivel = disponivel
        self.solicitado = solicitado
        super().__init__(f"Estoque insuficiente para {insumo_nome}: disponível {disponivel}, solicitado {solicitado}.")


@transaction.atomic
def registrar_movimento(
    *, insumo: Insumo, tipo: str, subtipo: str, quantidade: int,
    valor_unitario: Decimal | None = None, origem_tipo: str = "", origem_id=None,
    nota_fiscal_chave: str = "", nota_fiscal_numero: str = "", observacao: str = "",
    usuario=None,
) -> MovimentoEstoque:
    """Única função autorizada a mudar Insumo.qtd — sempre grava o
    MovimentoEstoque junto, na mesma transação. `select_for_update` evita
    corrida entre débitos concorrentes do mesmo insumo."""
    insumo_travado = Insumo.objects.select_for_update().get(pk=insumo.pk)

    if tipo == MovimentoEstoque.SD2_SAIDA and insumo_travado.qtd < quantidade:
        raise EstoqueInsuficienteError(insumo_travado.nome, insumo_travado.qtd, quantidade)

    if tipo == MovimentoEstoque.SD1_ENTRADA:
        delta = quantidade
    elif tipo == MovimentoEstoque.SD2_SAIDA:
        delta = -quantidade
    else:  # SD3 — sinal depende do subtipo
        delta = quantidade if subtipo == "ajuste_positivo" else -quantidade

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
    for item in itens:
        if item["quantidade"] <= 0:
            ignorados += 1
            continue

        qtd_inteira = round(item["quantidade"])
        valor = Decimal(str(item["valor_unitario"]))
        insumo = Insumo.objects.filter(codigo_barras=item["codigo_barras"]).first() if item["codigo_barras"] else None

        if insumo:
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
            if campos_alterados:
                insumo.save(update_fields=campos_alterados)

            registrar_movimento(
                insumo=insumo, tipo=MovimentoEstoque.SD1_ENTRADA, subtipo="nfe_fornecedor",
                quantidade=qtd_inteira, valor_unitario=valor,
                observacao=f"+{qtd_inteira} via XML de NF-e", usuario=usuario,
            )
            atualizados += 1
        else:
            insumo = Insumo.objects.create(
                nome=item["nome"], valor=valor, qtd=0,
                codigo_barras=item["codigo_barras"], lote=item["lote"] or "",
                data_validade=item["validade"], ncm=item["ncm"] or "",
                obs="Importado via XML de NF-e.",
            )
            registrar_movimento(
                insumo=insumo, tipo=MovimentoEstoque.SD1_ENTRADA, subtipo="nfe_fornecedor",
                quantidade=qtd_inteira, valor_unitario=valor,
                observacao="Criado via XML de NF-e", usuario=usuario,
            )
            criados += 1

    return {"criados": criados, "atualizados": atualizados, "ignorados": ignorados}


def alertas_estoque() -> dict:
    """Porte de dashboard.py:/estoque-alerta — limiar de estoque baixo (<3) e
    janela de validade (60 dias) vêm de settings (constantes do plano, §9)."""
    from datetime import date, timedelta

    from django.conf import settings

    hoje = date.today()
    return {
        "zerados": Insumo.objects.filter(qtd__lte=0),
        "baixos": Insumo.objects.filter(qtd__gt=0, qtd__lt=settings.ESTOQUE_BAIXO_LIMIAR),
        "vencidos": Insumo.objects.filter(data_validade__lt=hoje),
        "vencendo": Insumo.objects.filter(
            data_validade__gte=hoje,
            data_validade__lte=hoje + timedelta(days=settings.VALIDADE_ALERTA_DIAS),
        ),
    }
