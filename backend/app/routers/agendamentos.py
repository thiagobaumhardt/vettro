import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_usuario_atual
from ..database import get_db
from ..utils import get_or_404, montar_servicos

router = APIRouter(prefix="/api/agendamentos", tags=["agendamentos"], dependencies=[Depends(get_usuario_atual)])


def _resolver_paciente(db: Session, payload: schemas.AgendamentoIn):
    pac_nome, tutor_nome, tutor_tel = payload.pac_nome, payload.tutor_nome, payload.tutor_tel
    if payload.paciente_id:
        p = get_or_404(db, models.Paciente, payload.paciente_id, "Paciente")
        pac_nome = p.nome
        if p.tutor:
            tutor_nome, tutor_tel = p.tutor.nome, p.tutor.tel
    if not pac_nome:
        raise HTTPException(status_code=400, detail="Informe o nome do paciente.")
    return pac_nome, tutor_nome, tutor_tel


@router.get("", response_model=list[schemas.AgendamentoOut])
def listar(db: Session = Depends(get_db)):
    return db.query(models.Agendamento).order_by(models.Agendamento.data, models.Agendamento.hora).all()


@router.post("", response_model=schemas.AgendamentoOut, status_code=201)
def criar(payload: schemas.AgendamentoIn, db: Session = Depends(get_db)):
    pac_nome, tutor_nome, tutor_tel = _resolver_paciente(db, payload)
    servicos, _ = montar_servicos(db, payload.servico_ids)
    data = payload.model_dump(exclude={"servico_ids", "pac_nome", "tutor_nome", "tutor_tel"})
    obj = models.Agendamento(
        **data,
        pac_nome=pac_nome,
        tutor_nome=tutor_nome,
        tutor_tel=tutor_tel,
        servicos=servicos,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{id}", response_model=schemas.AgendamentoOut)
def atualizar(id: uuid.UUID, payload: schemas.AgendamentoIn, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Agendamento, id, "Agendamento")
    pac_nome, tutor_nome, tutor_tel = _resolver_paciente(db, payload)
    servicos, _ = montar_servicos(db, payload.servico_ids)
    data = payload.model_dump(exclude={"servico_ids", "pac_nome", "tutor_nome", "tutor_tel"})
    for k, v in data.items():
        setattr(obj, k, v)
    obj.pac_nome = pac_nome
    obj.tutor_nome = tutor_nome
    obj.tutor_tel = tutor_tel
    obj.servicos = servicos
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{id}/status", response_model=schemas.AgendamentoOut)
def alterar_status(id: uuid.UUID, payload: schemas.AgendamentoStatusIn, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Agendamento, id, "Agendamento")
    obj.status = payload.status
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{id}/reagendar", response_model=schemas.AgendamentoOut)
def reagendar(id: uuid.UUID, payload: schemas.AgendamentoReagendarIn, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Agendamento, id, "Agendamento")
    obj.data = payload.data
    obj.hora = payload.hora
    obj.status = "agendado"
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}", status_code=204)
def excluir(id: uuid.UUID, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Agendamento, id, "Agendamento")
    db.delete(obj)
    db.commit()
