"""Tabelas fiscais oficiais guardadas no próprio Vettro (apps/estoque/dados/),
pra cadastrar produto à mão sem saber código de cor — a clínica compra
avulso e nem sempre tem XML da nota de compra.

- ncm.json: tabela NCM do Siscomex (só os códigos de 8 dígitos), com a
  descrição completa montada da hierarquia (posição › subposição › item).
- cest.json: correlação CEST × NCM do Convênio ICMS 142/18 (CONFAZ). O NCM
  do convênio pode ser uma posição inteira ("3004" = todo 3004.xx.xx), então
  a busca é por prefixo — e um NCM pode ter mais de um CEST (a descrição
  decide).

Pra atualizar: substitua os dois arquivos (ver docs/tabelas-fiscais.md)."""
import json
import unicodedata
from functools import lru_cache
from pathlib import Path

DADOS = Path(__file__).resolve().parent / "dados"


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").lower()


@lru_cache(maxsize=1)
def _ncm():
    dados = json.loads((DADOS / "ncm.json").read_text(encoding="utf-8"))
    return dados["meta"], [(codigo, texto, _normalizar(texto)) for codigo, texto in dados["ncm"]]


@lru_cache(maxsize=1)
def _cest():
    return json.loads((DADOS / "cest.json").read_text(encoding="utf-8"))["cest"]


def formatar_ncm(codigo: str) -> str:
    return f"{codigo[:4]}.{codigo[4:6]}.{codigo[6:]}" if len(codigo) == 8 else codigo


def formatar_cest(codigo: str) -> str:
    return f"{codigo[:2]}.{codigo[2:5]}.{codigo[5:]}" if len(codigo) == 7 else codigo


def vigencia_ncm() -> str:
    return _ncm()[0].get("vigencia", "")


def descricao_ncm(codigo: str) -> str:
    codigo = "".join(filter(str.isdigit, codigo or ""))
    return next((texto for c, texto, _ in _ncm()[1] if c == codigo), "")


# A tabela usa o vocabulário oficial ("alimentos para cães", "xampus"); estes
# são os nomes do dia a dia de clínica/pet shop, trocados pelos termos dela.
SINONIMOS = {
    "racao": ["alimentos para caes", "alimentacao de animais"], "racoes": ["alimentos para caes", "alimentacao de animais"],
    "petisco": ["alimentos para caes"], "biscoito": ["alimentos para caes"], "sache": ["alimentos para caes"],
    "remedio": ["medicamentos"], "medicamento": ["medicamentos"], "vermifugo": ["medicamentos"], "antibiotico": ["medicamentos", "antibioticos"],
    "antiinflamatorio": ["medicamentos"], "anti-inflamatorio": ["medicamentos"], "analgesico": ["medicamentos"],
    "vacina": ["vacinas"], "antipulgas": ["inseticidas"], "pulga": ["inseticidas"], "carrapato": ["inseticidas"], "carrapaticida": ["inseticidas"],
    "shampoo": ["xampus"], "xampu": ["xampus"], "perfume": ["perfumes"], "colonia": ["aguas-de-colonia"],
    "coleira": ["artigos de seleiro", "coleiras"], "guia": ["artigos de seleiro"], "peitoral": ["artigos de seleiro"],
    "brinquedo": ["brinquedos"], "seringa": ["seringas"], "agulha": ["agulhas"], "luva": ["luvas"], "gaze": ["gazes"],
    "curativo": ["pensos", "ataduras"], "atadura": ["ataduras"], "algodao": ["algodao"], "termometro": ["termometros"],
    "comedouro": ["artigos de plastico", "obras de plastico"], "bebedouro": ["artigos de plastico", "obras de plastico"],
    "elizabetana": ["obras de plastico"], "suplemento": ["preparacoes do tipo utilizado na alimentacao de animais"],
}


# Capítulo/posição onde cada termo costuma estar — vem primeiro na lista.
PREFERENCIA = {
    "2309": ["racao", "racoes", "petisco", "biscoito", "sache", "suplemento"],
    "3004": ["remedio", "medicamento", "vermifugo", "antibiotico", "antiinflamatorio", "anti-inflamatorio", "analgesico",
             "antipulgas", "pulga", "carrapato", "carrapaticida"],
    "380891": ["antipulgas", "pulga", "carrapato", "carrapaticida"],
    "3002": ["vacina"], "3305": ["shampoo", "xampu"], "4201": ["coleira", "guia", "peitoral"],
    "3926": ["elizabetana", "comedouro", "bebedouro"], "9018": ["seringa", "agulha"], "3005": ["gaze", "curativo", "atadura"],
}


def _alternativas(palavra: str) -> list[str]:
    base = palavra[:-1] if len(palavra) > 4 and palavra.endswith("s") else palavra
    return [base] + SINONIMOS.get(palavra, []) + SINONIMOS.get(base, [])


def buscar_ncm(termo: str, limite: int = 12) -> list[dict]:
    """Por número (prefixo do código) ou por palavras. Cada palavra vale se ela
    (ou um sinônimo do SINONIMOS) aparece na descrição; vêm primeiro os que
    batem mais palavras, e os que batem no item (fim da descrição)."""
    termo = (termo or "").strip()
    digitos = "".join(filter(str.isdigit, termo))
    tabela = _ncm()[1]
    if digitos and len(digitos) >= 2 and len(digitos) == len(termo.replace(".", "").replace(" ", "")):
        achados = [(c, t) for c, t, _ in tabela if c.startswith(digitos)]
    else:
        palavras = [p for p in _normalizar(termo).split() if len(p) >= 3]
        if not palavras:
            return []
        grupos = [_alternativas(p) for p in palavras]
        bases = {p[:-1] if len(p) > 4 and p.endswith("s") else p for p in palavras} | set(palavras)
        preferidos = [pref for pref, termos in PREFERENCIA.items() if bases & set(termos)]
        candidatos = []
        for c, t, n in tabela:
            folha = n.rsplit("›", 1)[-1]
            batidas = sum(1 for g in grupos if any(a in n for a in g))
            preferido = any(c.startswith(pref) for pref in preferidos)
            if not batidas and not preferido:
                continue
            na_folha = sum(1 for g in grupos if any(a in folha for a in g))
            candidatos.append((not preferido, -batidas, -na_folha, c, t))
        achados = [(c, t) for *_, c, t in sorted(candidatos)]
    return [{"codigo": c, "formatado": formatar_ncm(c), "descricao": t} for c, t in achados[:limite]]


def cests_do_ncm(ncm: str) -> list[dict]:
    ncm = "".join(filter(str.isdigit, ncm or ""))
    if len(ncm) != 8:
        return []
    vistos, saida = set(), []
    for item in _cest():
        if ncm.startswith(item["prefixo"]) and (item["cest"], item["descricao"]) not in vistos:
            vistos.add((item["cest"], item["descricao"]))
            saida.append({**item, "formatado": formatar_cest(item["cest"])})
    return saida
