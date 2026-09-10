import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import get_usuario_atual
from ..database import get_db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(get_usuario_atual)])


@router.get("/stats", response_model=schemas.DashboardStats)
def stats(db: Session = Depends(get_db)):
    hoje = dt.date.today()
    return schemas.DashboardStats(
        tutores=db.query(models.Tutor).count(),
        pacientes=db.query(models.Paciente).count(),
        servicos=db.query(models.Servico).count(),
        insumos=db.query(models.Insumo).count(),
        atendimentos=db.query(models.Atendimento).count(),
        agendados=db.query(models.Agendamento)
        .filter(models.Agendamento.data >= hoje, models.Agendamento.status != "cancelado")
        .count(),
    )


@router.get("/estoque-alerta", response_model=schemas.EstoqueAlerta)
def estoque_alerta(db: Session = Depends(get_db)):
    insumos = db.query(models.Insumo).all()
    zerados = [i for i in insumos if i.qtd <= 0]
    baixos = [i for i in insumos if 0 < i.qtd < 3]
    return schemas.EstoqueAlerta(zerados=zerados, baixos=baixos)


@router.get("/ultimas-24h")
def ultimas_24h(db: Session = Depends(get_db)):
    hoje = dt.date.today()
    ontem = hoje - dt.timedelta(days=1)

    itens = []

    for a in (
        db.query(models.Atendimento)
        .filter(models.Atendimento.data >= ontem, models.Atendimento.data <= hoje)
        .all()
    ):
        itens.append(
            {
                "tipo": "modulo",
                "data": a.data.isoformat(),
                "hora": a.hora.isoformat(timespec="minutes") if a.hora else None,
                "pac_nome": a.pac_nome,
                "pac_especie": a.pac_especie,
                "tutor_nome": a.tutor_nome,
                "tutor_tel": a.tutor_tel,
                "servicos": a.servicos,
                "insumos": a.insumos,
                "total": float(a.total),
            }
        )

    for h in (
        db.query(models.AnamneseHist)
        .options(joinedload(models.AnamneseHist.paciente).joinedload(models.Paciente.tutor))
        .filter(models.AnamneseHist.data >= ontem, models.AnamneseHist.data <= hoje)
        .all()
    ):
        p = h.paciente
        itens.append(
            {
                "tipo": "ficha-atend",
                "data": h.data.isoformat(),
                "hora": h.hora.isoformat(timespec="minutes") if h.hora else None,
                "pac_nome": p.nome,
                "pac_especie": p.especie,
                "tutor_nome": p.tutor.nome if p.tutor else "",
                "tutor_tel": p.tutor.tel if p.tutor else "",
                "queixa": h.queixa,
                "servicos": h.servicos,
                "insumos": h.insumos,
                "total": float(h.total),
            }
        )

    for c in (
        db.query(models.CirurgiaHist)
        .options(joinedload(models.CirurgiaHist.paciente).joinedload(models.Paciente.tutor))
        .filter(models.CirurgiaHist.data >= ontem, models.CirurgiaHist.data <= hoje)
        .all()
    ):
        p = c.paciente
        itens.append(
            {
                "tipo": "cirurgia",
                "data": c.data.isoformat(),
                "hora": c.hora.isoformat(timespec="minutes") if c.hora else None,
                "pac_nome": p.nome,
                "pac_especie": p.especie,
                "tutor_nome": p.tutor.nome if p.tutor else "",
                "tutor_tel": p.tutor.tel if p.tutor else "",
                "proc": c.proc,
                "servicos": c.procedimentos,
                "insumos": c.insumos,
                "total": float(c.total),
            }
        )

    itens.sort(key=lambda x: (x["data"], x["hora"] or "99:99"), reverse=True)
    return itens
