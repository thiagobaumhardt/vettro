import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_usuario_atual
from ..database import get_db
from ..utils import get_or_404

router = APIRouter(prefix="/api/cirurgias-cat", tags=["cirurgias-cat"], dependencies=[Depends(get_usuario_atual)])


def _validar(payload: schemas.CirurgiaCategoriaIn):
    if payload.valor_p is None and payload.valor_m is None and payload.valor_g is None:
        raise HTTPException(status_code=422, detail="Informe pelo menos um valor por faixa de peso.")


@router.get("", response_model=list[schemas.CirurgiaCategoriaOut])
def listar(db: Session = Depends(get_db)):
    return db.query(models.CirurgiaCategoria).order_by(models.CirurgiaCategoria.nome).all()


@router.post("", response_model=schemas.CirurgiaCategoriaOut, status_code=201)
def criar(payload: schemas.CirurgiaCategoriaIn, db: Session = Depends(get_db)):
    _validar(payload)
    obj = models.CirurgiaCategoria(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{id}", response_model=schemas.CirurgiaCategoriaOut)
def atualizar(id: uuid.UUID, payload: schemas.CirurgiaCategoriaIn, db: Session = Depends(get_db)):
    _validar(payload)
    obj = get_or_404(db, models.CirurgiaCategoria, id, "Procedimento")
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}", status_code=204)
def excluir(id: uuid.UUID, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.CirurgiaCategoria, id, "Procedimento")
    db.delete(obj)
    db.commit()
