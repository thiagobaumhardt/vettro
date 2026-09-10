import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_usuario_atual
from ..database import get_db
from ..utils import get_or_404

router = APIRouter(prefix="/api/insumos", tags=["insumos"], dependencies=[Depends(get_usuario_atual)])


@router.get("", response_model=list[schemas.InsumoOut])
def listar(db: Session = Depends(get_db)):
    return db.query(models.Insumo).order_by(models.Insumo.nome).all()


@router.post("", response_model=schemas.InsumoOut, status_code=201)
def criar(payload: schemas.InsumoIn, db: Session = Depends(get_db)):
    obj = models.Insumo(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{id}", response_model=schemas.InsumoOut)
def atualizar(id: uuid.UUID, payload: schemas.InsumoIn, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Insumo, id, "Insumo")
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}", status_code=204)
def excluir(id: uuid.UUID, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Insumo, id, "Insumo")
    db.delete(obj)
    db.commit()


@router.patch("/{id}/repor", response_model=schemas.InsumoOut)
def repor(id: uuid.UUID, payload: schemas.ReporIn, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Insumo, id, "Insumo")
    obj.qtd += payload.qtd
    db.commit()
    db.refresh(obj)
    return obj
