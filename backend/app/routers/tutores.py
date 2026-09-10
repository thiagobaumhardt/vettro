import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_usuario_atual
from ..database import get_db
from ..utils import get_or_404

router = APIRouter(prefix="/api/tutores", tags=["tutores"], dependencies=[Depends(get_usuario_atual)])


@router.get("", response_model=list[schemas.TutorOut])
def listar(busca: str = "", db: Session = Depends(get_db)):
    q = db.query(models.Tutor)
    if busca:
        like = f"%{busca}%"
        q = q.filter(or_(models.Tutor.nome.ilike(like), models.Tutor.tel.ilike(like)))
    return q.order_by(models.Tutor.criado_em.desc()).all()


@router.post("", response_model=schemas.TutorOut, status_code=201)
def criar(payload: schemas.TutorIn, db: Session = Depends(get_db)):
    obj = models.Tutor(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{tutor_id}", response_model=schemas.TutorOut)
def obter(tutor_id: uuid.UUID, db: Session = Depends(get_db)):
    return get_or_404(db, models.Tutor, tutor_id, "Tutor")


@router.put("/{tutor_id}", response_model=schemas.TutorOut)
def atualizar(tutor_id: uuid.UUID, payload: schemas.TutorIn, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Tutor, tutor_id, "Tutor")
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{tutor_id}", status_code=204)
def excluir(tutor_id: uuid.UUID, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Tutor, tutor_id, "Tutor")
    db.delete(obj)
    db.commit()


@router.get("/{tutor_id}/pacientes", response_model=list[schemas.PacienteOut])
def pacientes_do_tutor(tutor_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.query(models.Paciente).filter(models.Paciente.tutor_id == tutor_id).all()
