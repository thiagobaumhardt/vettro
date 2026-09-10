import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_usuario_atual
from ..database import get_db
from ..utils import get_or_404

router = APIRouter(prefix="/api/pacientes", tags=["pacientes"], dependencies=[Depends(get_usuario_atual)])


@router.get("", response_model=list[schemas.PacienteOut])
def listar(busca: str = "", db: Session = Depends(get_db)):
    q = db.query(models.Paciente).outerjoin(models.Tutor)
    if busca:
        like = f"%{busca}%"
        q = q.filter(or_(models.Paciente.nome.ilike(like), models.Tutor.nome.ilike(like)))
    return q.order_by(models.Paciente.criado_em.desc()).all()


@router.post("", response_model=schemas.PacienteOut, status_code=201)
def criar(payload: schemas.PacienteIn, db: Session = Depends(get_db)):
    obj = models.Paciente(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{id}", response_model=schemas.PacienteOut)
def obter(id: uuid.UUID, db: Session = Depends(get_db)):
    return get_or_404(db, models.Paciente, id, "Paciente")


@router.put("/{id}", response_model=schemas.PacienteOut)
def atualizar(id: uuid.UUID, payload: schemas.PacienteIn, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Paciente, id, "Paciente")
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}", status_code=204)
def excluir(id: uuid.UUID, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Paciente, id, "Paciente")
    db.delete(obj)
    db.commit()


@router.put("/{id}/foto", response_model=schemas.PacienteOut)
def atualizar_foto(id: uuid.UUID, payload: dict, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Paciente, id, "Paciente")
    obj.foto_perfil = payload.get("foto_perfil")
    db.commit()
    db.refresh(obj)
    return obj
