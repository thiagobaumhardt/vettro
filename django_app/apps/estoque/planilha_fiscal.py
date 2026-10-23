"""Planilha fiscal dos produtos (Estoque → Planilha fiscal, só admin).

A clínica compra avulso e cadastra à mão; o contador (Fox) confere os dados
fiscais de todos os produtos de uma vez: o Vettro exporta um CSV (abre no
Excel, separado por ";"), o contador corrige NCM/CEST/ST/monofásico/origem e
a clínica importa de volta. O produto é achado pelo Código (001, 002...) —
nome e demais colunas são só pra leitura e não são alterados."""
import csv
import io

from django.db import transaction

from .models import ORIGEM_CHOICES, Insumo
from .tabelas_fiscais import descricao_ncm, formatar_cest, formatar_ncm

COLUNAS = [
    "Código", "Produto", "Finalidade", "Unidade na nota", "Código de barras",
    "NCM", "Descrição do NCM", "CEST", "Substituição tributária", "PIS/COFINS monofásico", "Origem",
]
ORIGENS = {v for v, _ in ORIGEM_CHOICES}
SIM = {"sim", "s", "x", "1", "true", "verdadeiro"}
NAO = {"nao", "não", "n", "0", "false", "falso", ""}


def exportar() -> bytes:
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";")
    escritor.writerow(COLUNAS)
    for i in Insumo.objects.order_by("codigo", "nome"):
        escritor.writerow([
            i.codigo or "", i.nome, i.get_finalidade_display(), i.unidade_nota, i.codigo_barras or "",
            formatar_ncm(i.ncm) if i.ncm else "", descricao_ncm(i.ncm) if i.ncm else "",
            formatar_cest(i.cest) if i.cest else "", "Sim" if i.tem_st else "Não",
            "Sim" if i.pis_cofins_monofasico else "Não", i.origem,
        ])
    # BOM: o Excel abre com acento certo.
    return ("﻿" + saida.getvalue()).encode("utf-8")


def _texto(conteudo: bytes) -> str:
    for codificacao in ("utf-8-sig", "cp1252"):  # Excel salva CSV em cp1252 no Windows
        try:
            return conteudo.decode(codificacao)
        except UnicodeDecodeError:
            continue
    raise ValueError("Não foi possível ler o arquivo — salve como CSV (separado por ponto e vírgula).")


def _sim_nao(valor: str, coluna: str):
    v = (valor or "").strip().lower()
    if v in SIM:
        return True
    if v in NAO:
        return False
    raise ValueError(f'{coluna}: use "Sim" ou "Não" (veio "{valor}")')


@transaction.atomic
def importar(conteudo: bytes) -> dict:
    """Aplica as colunas fiscais. Linha com erro é pulada (as outras entram)."""
    texto = _texto(conteudo)
    delimitador = ";" if texto.splitlines()[0].count(";") >= texto.splitlines()[0].count(",") else ","
    leitor = csv.DictReader(io.StringIO(texto), delimiter=delimitador)
    faltando = [c for c in ("Código", "NCM", "CEST") if c not in (leitor.fieldnames or [])]
    if faltando:
        raise ValueError(f"Colunas não encontradas: {', '.join(faltando)}. Use a planilha exportada pelo Vettro.")

    alterados, erros, sem_mudanca = [], [], 0
    for numero, linha in enumerate(leitor, start=2):
        codigo = (linha.get("Código") or "").strip()
        if not codigo:
            continue
        insumo = Insumo.objects.filter(codigo=codigo).first()
        if insumo is None:
            erros.append((numero, codigo, "código não existe no Vettro"))
            continue
        try:
            ncm = "".join(filter(str.isdigit, linha.get("NCM") or ""))
            if ncm and len(ncm) != 8:
                raise ValueError(f"NCM precisa de 8 dígitos (veio {linha.get('NCM')})")
            if ncm and not descricao_ncm(ncm):
                raise ValueError(f"NCM {formatar_ncm(ncm)} não existe na tabela oficial vigente")
            cest = "".join(filter(str.isdigit, linha.get("CEST") or ""))
            if cest and len(cest) != 7:
                raise ValueError(f"CEST precisa de 7 dígitos (veio {linha.get('CEST')})")
            novos = {"ncm": ncm, "cest": cest}
            if "Substituição tributária" in linha:
                novos["tem_st"] = _sim_nao(linha["Substituição tributária"], "Substituição tributária")
            if "PIS/COFINS monofásico" in linha:
                novos["pis_cofins_monofasico"] = _sim_nao(linha["PIS/COFINS monofásico"], "PIS/COFINS monofásico")
            origem = (linha.get("Origem") or "").strip()
            if origem:
                if origem not in ORIGENS:
                    raise ValueError(f"Origem precisa ser de 0 a 8 (veio {origem})")
                novos["origem"] = origem
            if novos.get("tem_st") and not cest:
                raise ValueError("com substituição tributária precisa de CEST")
        except ValueError as exc:
            erros.append((numero, codigo, str(exc)))
            continue
        mudou = [campo for campo, valor in novos.items() if getattr(insumo, campo) != valor]
        if not mudou:
            sem_mudanca += 1
            continue
        for campo in mudou:
            setattr(insumo, campo, novos[campo])
        insumo.save(update_fields=mudou)
        alterados.append((insumo.codigo, insumo.nome, mudou))
    return {"alterados": alterados, "erros": erros, "sem_mudanca": sem_mudanca}
