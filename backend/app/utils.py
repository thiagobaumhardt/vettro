import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models


def get_or_404(db: Session, model, id: uuid.UUID, name: str = "Registro"):
    obj = db.get(model, id)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{name} não encontrado.")
    return obj


def cpf_valido(cpf: str) -> bool:
    """Valida CPF pelo algoritmo oficial de dígitos verificadores (módulo 11)."""
    d = "".join(c for c in cpf if c.isdigit())
    if len(d) != 11 or d == d[0] * 11:
        return False
    for i in (9, 10):
        soma = sum(int(d[num]) * ((i + 1) - num) for num in range(i))
        dv = (soma * 10 % 11) % 10
        if dv != int(d[i]):
            return False
    return True


def validar_tamanho_base64(data_url: str | None, max_bytes: int, campo: str):
    """Valida o tamanho de um payload base64 (data URL) no servidor — o limite no
    navegador é só UX, precisa ser reforçado aqui para não ser contornável via API direta."""
    if not data_url:
        return
    payload = data_url.split(",", 1)[-1]
    tamanho_aprox = len(payload) * 3 // 4
    if tamanho_aprox > max_bytes:
        raise HTTPException(status_code=400, detail=f"{campo} excede o tamanho máximo de {max_bytes // (1024 * 1024)} MB.")


def registrar_auditoria(
    db: Session,
    usuario: "models.Usuario | None",
    acao: str,
    entidade: str,
    entidade_id: uuid.UUID | None = None,
    detalhe: str | None = None,
    ip: str | None = None,
):
    db.add(
        models.AuditLog(
            usuario_id=usuario.id if usuario else None,
            usuario_nome=usuario.nome if usuario else None,
            acao=acao,
            entidade=entidade,
            entidade_id=entidade_id,
            detalhe=detalhe,
            ip=ip,
        )
    )


def montar_servicos(db: Session, servico_ids: list[uuid.UUID]) -> tuple[list[dict], float]:
    total = 0.0
    itens = []
    for sid in servico_ids:
        s = get_or_404(db, models.Servico, sid, "Serviço")
        valor = float(s.valor)
        itens.append({"id": str(s.id), "nome": s.nome, "valor": valor})
        total += valor
    return itens, total


def montar_insumos(db: Session, usos: list) -> tuple[list[dict], float, list[tuple[models.Insumo, int]]]:
    """Valida disponibilidade em estoque e retorna (snapshot, total, [(insumo, qtd)]) para posterior débito."""
    total = 0.0
    itens = []
    debitos = []
    for uso in usos:
        i = get_or_404(db, models.Insumo, uso.id, "Insumo")
        if uso.qtd > (i.qtd or 0):
            raise HTTPException(
                status_code=400,
                detail=f'Estoque insuficiente: "{i.nome}" (disponível: {i.qtd or 0})',
            )
        valor = float(i.valor)
        itens.append({"id": str(i.id), "nome": i.nome, "valor": valor, "qtd": uso.qtd})
        total += valor * uso.qtd
        debitos.append((i, uso.qtd))
    return itens, total, debitos


def debitar_estoque(debitos: list[tuple]):
    for insumo, qtd in debitos:
        insumo.qtd -= qtd


def valor_por_peso(cat, peso: float) -> float:
    p = float(peso or 0)
    vp = float(cat.valor_p) if cat.valor_p is not None else None
    vm = float(cat.valor_m) if cat.valor_m is not None else None
    vg = float(cat.valor_g) if cat.valor_g is not None else None
    if 0 < p < 10:
        return vp or 0
    if 10 <= p <= 25:
        return vm or 0
    if p > 25:
        return vg or 0
    return vp or vm or vg or 0
