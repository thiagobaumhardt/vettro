"""Pacote mensal pra contabilidade (pedido do contador): XMLs autorizados e de
cancelamento + relatório separando a receita de serviços (NFS-e) da de
vendas de produtos (NFC-e), por item."""
import csv
import io
import zipfile
from datetime import date
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from .models import NotaFiscalEmitida


def notas_do_mes(ano: int, mes: int):
    inicio = date(ano, mes, 1)
    fim = date(ano + (mes == 12), mes % 12 + 1, 1)
    return (NotaFiscalEmitida.objects.filter(status__in=["emitida", "cancelada"])
            .filter(emitida_em__date__gte=inicio, emitida_em__date__lt=fim).order_by("tipo", "emitida_em"))


def resumo(notas) -> dict:
    def bloco(tipo):
        doc = notas.filter(tipo=tipo)
        agg = doc.aggregate(
            qtd=Count("id", filter=Q(status="emitida")), total=Sum("valor_total", filter=Q(status="emitida")),
            canceladas=Count("id", filter=Q(status="cancelada")),
        )
        return {"qtd": agg["qtd"], "total": agg["total"] or Decimal("0"), "canceladas": agg["canceladas"]}

    return {"servicos": bloco("nfse"), "vendas": bloco("nfce"), "simulacao": notas.filter(simulacao=True).exists()}


def _brl(valor) -> str:
    return f"{Decimal(str(valor or 0)):.2f}".replace(".", ",")


def _nome_arquivo(nota) -> str:
    return f"{nota.numero or 'sem-numero'}-{nota.chave_acesso or nota.pk}"


def relatorio_csv(notas) -> str:
    """Uma linha por item de nota (separador ";" e vírgula decimal, abre direto no Excel)."""
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";")
    escritor.writerow([
        "Receita", "Documento", "Número", "Emissão", "Situação", "Chave de acesso",
        "Código", "Descrição", "NCM / Cód. nacional", "CFOP", "CSOSN", "Qtd", "Unidade", "Valor do item", "Total da nota",
    ])
    for nota in notas:
        receita = "Serviços" if nota.tipo == "nfse" else "Venda de produtos"
        emissao = timezone.localtime(nota.emitida_em).strftime("%d/%m/%Y %H:%M") if nota.emitida_em else ""
        for item in nota.dados.get("itens", []):
            escritor.writerow([
                receita, nota.get_tipo_display(), nota.numero, emissao, nota.get_status_display(), nota.chave_acesso,
                item.get("codigo", ""), item.get("descricao", ""), item.get("ncm") or item.get("codigo_nacional", ""),
                item.get("cfop", ""), item.get("cst_csosn", ""), str(item.get("qtd", "")).replace(".", ","),
                item.get("unidade", ""), _brl(item.get("valor")), _brl(nota.valor_total),
            ])
    return saida.getvalue()


def gerar_zip(ano: int, mes: int, clinica_nome: str) -> bytes:
    notas = list(notas_do_mes(ano, mes))
    dados = resumo(notas_do_mes(ano, mes))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for nota in notas:
            pasta = "NFS-e" if nota.tipo == "nfse" else "NFC-e"
            if nota.xml:
                zf.writestr(f"{pasta}/autorizadas/{_nome_arquivo(nota)}.xml", nota.xml)
            if nota.status == "cancelada" and nota.xml_cancelamento:
                zf.writestr(f"{pasta}/canceladas/{_nome_arquivo(nota)}-cancelamento.xml", nota.xml_cancelamento)
        # utf-8 com BOM: o Excel abre os acentos certos.
        zf.writestr("relatorio_itens.csv", "﻿" + relatorio_csv(notas))
        linhas = [
            f"{clinica_nome} — notas fiscais de {mes:02d}/{ano}",
            "",
            f"Receita de serviços (NFS-e): {dados['servicos']['qtd']} nota(s), R$ {_brl(dados['servicos']['total'])}"
            f" · {dados['servicos']['canceladas']} cancelada(s)",
            f"Receita de vendas de produtos (NFC-e): {dados['vendas']['qtd']} nota(s), R$ {_brl(dados['vendas']['total'])}"
            f" · {dados['vendas']['canceladas']} cancelada(s)",
            "",
            "Pastas: autorizadas = XML da nota; canceladas = XML do evento de cancelamento.",
            "relatorio_itens.csv: uma linha por item, separando serviços e vendas.",
        ]
        if dados["simulacao"]:
            linhas += ["", "ATENÇÃO: há notas de SIMULAÇÃO (sem valor fiscal) neste pacote — emissor real ainda não ligado."]
        zf.writestr("LEIA-ME.txt", "\r\n".join(linhas))
    return buffer.getvalue()
