import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_usuario_atual
from ..database import get_db
from ..utils import debitar_estoque, get_or_404, montar_insumos, montar_servicos

router = APIRouter(tags=["anamnese"], dependencies=[Depends(get_usuario_atual)])


@router.get("/api/pacientes/{paciente_id}/anamnese", response_model=list[schemas.AnamneseOut])
def listar(paciente_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(models.AnamneseHist)
        .filter(models.AnamneseHist.paciente_id == paciente_id)
        .order_by(models.AnamneseHist.criado_em.desc())
        .all()
    )


@router.post("/api/pacientes/{paciente_id}/anamnese", response_model=schemas.AnamneseOut, status_code=201)
def criar(paciente_id: uuid.UUID, payload: schemas.AnamneseIn, db: Session = Depends(get_db)):
    paciente = get_or_404(db, models.Paciente, paciente_id, "Paciente")

    servicos, total_serv = montar_servicos(db, payload.servico_ids)
    insumos, total_ins, debitos = montar_insumos(db, payload.insumos)

    total = total_serv + total_ins
    if payload.plantao and total_serv > 0:
        acrescimo = total_serv * 0.5
        total += acrescimo
        servicos_cobranca = servicos + [{"id": str(uuid.uuid4()), "nome": "🌙 Plantão (+50%)", "valor": acrescimo}]
    else:
        servicos_cobranca = servicos

    data = payload.model_dump(exclude={"servico_ids", "insumos"})
    obj = models.AnamneseHist(
        paciente_id=paciente_id,
        **data,
        servicos=servicos,
        insumos=insumos,
        total=total,
    )
    db.add(obj)

    if servicos or insumos:
        debitar_estoque(debitos)
        cobranca = models.Cobranca(
            paciente_id=paciente_id,
            servicos=servicos_cobranca,
            insumos=insumos,
            obs="",
            total=total,
            status="pendente",
            tutor_nome=paciente.tutor.nome if paciente.tutor else "",
        )
        db.add(cobranca)

    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/api/anamnese/{id}", status_code=204)
def excluir(id: uuid.UUID, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.AnamneseHist, id, "Registro de atendimento")
    db.delete(obj)
    db.commit()
