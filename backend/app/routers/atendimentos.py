import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_usuario_atual
from ..database import get_db
from ..utils import debitar_estoque, get_or_404, montar_insumos, montar_servicos

router = APIRouter(prefix="/api/atendimentos", tags=["atendimentos"], dependencies=[Depends(get_usuario_atual)])


@router.get("", response_model=list[schemas.AtendimentoOut])
def listar(db: Session = Depends(get_db)):
    return db.query(models.Atendimento).order_by(models.Atendimento.criado_em.desc()).all()


@router.post("", response_model=schemas.AtendimentoOut, status_code=201)
def criar(payload: schemas.AtendimentoIn, db: Session = Depends(get_db)):
    paciente = get_or_404(db, models.Paciente, payload.paciente_id, "Paciente")

    servicos, total_serv = montar_servicos(db, payload.servico_ids)
    insumos, total_ins, debitos = montar_insumos(db, payload.insumos)
    total = total_serv + total_ins
    if payload.plantao and total_serv > 0:
        total += total_serv * 0.5

    debitar_estoque(debitos)

    obj = models.Atendimento(
        paciente_id=paciente.id,
        pac_nome=paciente.nome,
        pac_especie=paciente.especie,
        tutor_nome=paciente.tutor.nome if paciente.tutor else "",
        tutor_tel=paciente.tutor.tel if paciente.tutor else "",
        data=payload.data,
        hora=payload.hora,
        servicos=servicos,
        insumos=insumos,
        plantao=payload.plantao,
        obs=payload.obs,
        total=total,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}", status_code=204)
def excluir(id: uuid.UUID, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Atendimento, id, "Atendimento")
    db.delete(obj)
    db.commit()
