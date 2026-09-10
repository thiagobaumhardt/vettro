import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import require_admin
from ..database import get_db
from ..utils import debitar_estoque, get_or_404, montar_insumos, montar_servicos

# Módulo de faturamento: restrito ao papel admin (veterinárias nominais não têm acesso).
router = APIRouter(tags=["cobrancas"], dependencies=[Depends(require_admin)])


@router.get("/api/pacientes/{paciente_id}/cobrancas", response_model=list[schemas.CobrancaOut])
def listar(paciente_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(models.Cobranca)
        .filter(models.Cobranca.paciente_id == paciente_id)
        .order_by(models.Cobranca.criado_em.desc())
        .all()
    )


@router.post("/api/pacientes/{paciente_id}/cobrancas", response_model=schemas.CobrancaOut, status_code=201)
def criar(paciente_id: uuid.UUID, payload: schemas.CobrancaIn, db: Session = Depends(get_db)):
    paciente = get_or_404(db, models.Paciente, paciente_id, "Paciente")

    servicos, total_serv = montar_servicos(db, payload.servico_ids)
    insumos, total_ins, debitos = montar_insumos(db, payload.insumos)
    total = total_serv + total_ins

    if not servicos and not insumos:
        raise HTTPException(status_code=400, detail="Selecione ao menos um item.")

    debitar_estoque(debitos)
    obj = models.Cobranca(
        paciente_id=paciente_id,
        servicos=servicos,
        insumos=insumos,
        obs=payload.obs,
        total=total,
        status="pendente",
        tutor_nome=paciente.tutor.nome if paciente.tutor else "",
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/api/cobrancas/{id}/pagar", response_model=schemas.CobrancaOut)
def marcar_pago(id: uuid.UUID, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Cobranca, id, "Cobrança")
    obj.status = "pago"
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/api/cobrancas/{id}", status_code=204)
def excluir(id: uuid.UUID, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Cobranca, id, "Cobrança")
    db.delete(obj)
    db.commit()
