"""Financeiro (menu Financeiro, só admin): entradas e saídas de um período.

Entradas não são lançadas à mão — saem do que já existe no sistema:
- recebimento na recepção (Recebimento + PagamentoRecebimento, por forma);
- baixa manual de cobrança feita pelo admin (Cobranca paga sem recebimento);
- venda de balcão paga e não cancelada (Venda).
Saídas: as despesas lançadas em Financeiro → Saídas (Despesa) + a REPOSIÇÃO
DE ESTOQUE, automática — entrada SD1 por XML de NF-e (uma linha por nota) ou
manual (uma linha por entrada), pelo custo lançado. Entrada que não foi compra
(estoque inicial, doação) fica de fora: `MovimentoEstoque.fora_do_financeiro`,
marcado na entrada manual ou pelo botão "Não é compra" no Financeiro."""
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

from .models import Cobranca, Despesa, PagamentoRecebimento, Recebimento

FORMAS = dict(PagamentoRecebimento.FORMA_CHOICES)


@dataclass
class Entrada:
    quando: object  # datetime
    origem: str
    descricao: str
    pessoa: str
    forma: str
    valor: Decimal
    link: str = ""


def entradas(inicio: date, fim: date) -> list[Entrada]:
    from apps.vendas.models import Venda

    itens = []
    for r in Recebimento.objects.filter(criado_em__date__range=(inicio, fim)).prefetch_related("pagamentos"):
        itens.append(Entrada(
            quando=r.criado_em, origem="Recepção", descricao=f"Recebimento {r.numero}", pessoa=r.tutor_nome,
            forma=r.formas_texto, valor=r.total, link=reverse("recepcao:recibo", args=[r.pk]),
        ))
    baixas = Cobranca.objects.filter(status="pago", recebimento__isnull=True, pago_em__date__range=(inicio, fim)).select_related("paciente")
    for c in baixas:
        itens.append(Entrada(
            quando=c.pago_em, origem="Baixa de cobrança", descricao=f"Cobrança de {c.paciente.nome}" if c.paciente_id else "Cobrança",
            pessoa=c.tutor_nome, forma="Baixa manual", valor=c.valor_pago if c.valor_pago is not None else c.total,
            link=(reverse("pacientes:ficha", args=[c.paciente_id]) + "?aba=cobranca") if c.paciente_id else "",
        ))
    vendas = Venda.objects.filter(pagamento_status="pago", cancelada_em__isnull=True, criado_em__date__range=(inicio, fim))
    for v in vendas:
        forma = v.get_forma_pagamento_display() + (f" em {v.parcelas}x" if v.parcelas > 1 else "")
        itens.append(Entrada(
            quando=v.criado_em, origem="Venda", descricao=f"Venda {v.numero}", pessoa=v.cliente_nome or "Consumidor",
            forma=forma, valor=v.total, link=reverse("vendas:detalhe", args=[v.pk]),
        ))
    return sorted(itens, key=lambda e: e.quando, reverse=True)


def entradas_por_forma(inicio: date, fim: date) -> list[tuple[str, Decimal]]:
    """Recepção pelo que foi pago em cada forma (um recebimento pode ter 2
    cartões + Pix); venda pela forma dela; baixa manual numa linha própria."""
    from apps.vendas.models import Venda

    total = defaultdict(Decimal)
    pagos = PagamentoRecebimento.objects.filter(recebimento__criado_em__date__range=(inicio, fim))
    for linha in pagos.values("forma").annotate(s=Sum("valor")):
        total[FORMAS.get(linha["forma"], linha["forma"])] += linha["s"] or 0
    vendas = Venda.objects.filter(pagamento_status="pago", cancelada_em__isnull=True, criado_em__date__range=(inicio, fim))
    for linha in vendas.values("forma_pagamento").annotate(s=Sum("total")):
        total[FORMAS.get(linha["forma_pagamento"], linha["forma_pagamento"])] += linha["s"] or 0
    baixas = Cobranca.objects.filter(status="pago", recebimento__isnull=True, pago_em__date__range=(inicio, fim))
    soma_baixas = sum((c.valor_pago if c.valor_pago is not None else c.total) for c in baixas)
    if soma_baixas:
        total["Baixa manual"] += soma_baixas
    return sorted(total.items(), key=lambda kv: kv[1], reverse=True)


def saidas(inicio: date, fim: date):
    return Despesa.objects.filter(data__range=(inicio, fim))


@dataclass
class Reposicao:
    chave: str  # "nf:<chave ou número>" ou "mov:<id>" — usado pelo botão "Não é compra"
    data: date
    descricao: str
    detalhe: str
    valor: Decimal
    sem_custo: bool = False


def _emitente(observacao: str) -> str:
    achado = re.search(r"\(emitente (.+?)\)", observacao or "")
    return achado.group(1) if achado else ""


def movimentos_reposicao(chave: str):
    """Movimentos SD1 de uma linha de reposição (todos os itens da nota, ou a entrada manual)."""
    from apps.estoque.models import MovimentoEstoque

    tipo, _, valor = chave.partition(":")
    base = MovimentoEstoque.objects.filter(tipo=MovimentoEstoque.SD1_ENTRADA, subtipo__in=("nfe_fornecedor", "manual_sem_nota"))
    if tipo == "nf":
        return base.filter(subtipo="nfe_fornecedor").filter(nota_fiscal_chave=valor) if len(valor) == 44 \
            else base.filter(subtipo="nfe_fornecedor", nota_fiscal_chave="", nota_fiscal_numero=valor)
    return base.filter(pk=valor) if tipo == "mov" else base.none()


def reposicoes(inicio: date, fim: date, *, ignoradas: bool = False) -> list[Reposicao]:
    from apps.estoque.models import MovimentoEstoque

    movimentos = (MovimentoEstoque.objects
                  .filter(tipo=MovimentoEstoque.SD1_ENTRADA, subtipo__in=("nfe_fornecedor", "manual_sem_nota"),
                          criado_em__date__range=(inicio, fim), fora_do_financeiro=ignoradas)
                  .select_related("insumo").order_by("criado_em"))
    notas, linhas = {}, []
    for m in movimentos:
        custo = (m.valor_unitario or 0) * m.quantidade
        if m.subtipo == "nfe_fornecedor":
            ident = m.nota_fiscal_chave or m.nota_fiscal_numero or str(m.pk)
            linha = notas.get(ident)
            if linha is None:
                emitente = _emitente(m.observacao)
                linha = notas[ident] = Reposicao(
                    chave=f"nf:{ident}" if (m.nota_fiscal_chave or m.nota_fiscal_numero) else f"mov:{m.pk}",
                    data=timezone.localtime(m.criado_em).date(),
                    descricao=f"NF-e {m.nota_fiscal_numero}" if m.nota_fiscal_numero else "NF-e de compra",
                    detalhe=emitente, valor=Decimal("0"),
                )
                linhas.append(linha)
            linha.valor += custo
            linha.sem_custo = linha.sem_custo or m.valor_unitario is None
        else:
            linhas.append(Reposicao(
                chave=f"mov:{m.pk}", data=timezone.localtime(m.criado_em).date(),
                descricao=f"Entrada manual: {m.insumo.nome}", detalhe=m.observacao, valor=custo,
                sem_custo=m.valor_unitario is None,
            ))
    for linha in linhas:
        linha.valor = linha.valor.quantize(Decimal("0.01"))
    return sorted(linhas, key=lambda r: r.data, reverse=True)


def saidas_por_categoria(inicio: date, fim: date, reposicao_total: Decimal = Decimal("0")) -> list[tuple[str, Decimal]]:
    rotulos = dict(Despesa.CATEGORIA_CHOICES)
    linhas = saidas(inicio, fim).values("categoria").annotate(s=Sum("valor")).order_by("-s")
    resultado = [(rotulos.get(l["categoria"], l["categoria"]), l["s"]) for l in linhas]
    if reposicao_total:
        resultado.append(("Reposição de estoque", reposicao_total))
    return sorted(resultado, key=lambda kv: kv[1], reverse=True)


def periodo(get) -> tuple[date, date, str]:
    """?mes=2026-10 (padrão: mês atual) ou ?de=...&ate=... (datas ISO)."""
    hoje = timezone.localdate()
    try:
        if get.get("de") and get.get("ate"):
            inicio, fim = date.fromisoformat(get["de"]), date.fromisoformat(get["ate"])
            if inicio > fim:
                inicio, fim = fim, inicio
            return inicio, fim, ""
        ano, mes = (int(x) for x in (get.get("mes") or f"{hoje:%Y-%m}").split("-"))
        inicio = date(ano, mes, 1)
    except ValueError:
        inicio = hoje.replace(day=1)
    proximo = date(inicio.year + (inicio.month == 12), inicio.month % 12 + 1, 1)
    return inicio, date.fromordinal(proximo.toordinal() - 1), f"{inicio:%Y-%m}"
