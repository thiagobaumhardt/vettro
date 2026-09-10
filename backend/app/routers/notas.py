import datetime as dt
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_usuario_atual
from ..database import get_db
from ..utils import get_or_404

router = APIRouter(tags=["notas"], dependencies=[Depends(get_usuario_atual)])


@router.get("/api/pacientes/{paciente_id}/notas", response_model=list[schemas.NotaOut])
def listar(paciente_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(models.Nota)
        .filter(models.Nota.paciente_id == paciente_id)
        .order_by(models.Nota.criado_em.desc())
        .all()
    )


@router.post("/api/pacientes/{paciente_id}/notas", response_model=schemas.NotaOut, status_code=201)
def criar(paciente_id: uuid.UUID, payload: schemas.NotaIn, db: Session = Depends(get_db)):
    get_or_404(db, models.Paciente, paciente_id, "Paciente")
    obj = models.Nota(paciente_id=paciente_id, **payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/api/notas/{id}", response_model=schemas.NotaOut)
def atualizar(id: uuid.UUID, payload: schemas.NotaIn, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Nota, id, "Anotação")
    obj.titulo = payload.titulo
    obj.conteudo = payload.conteudo
    obj.editado_em = dt.datetime.now(dt.timezone.utc)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/api/notas/{id}", status_code=204)
def excluir(id: uuid.UUID, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Nota, id, "Anotação")
    db.delete(obj)
    db.commit()
