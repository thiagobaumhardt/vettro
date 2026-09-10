import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_usuario_atual
from ..database import get_db
from ..utils import get_or_404

router = APIRouter(prefix="/api/servicos", tags=["servicos"], dependencies=[Depends(get_usuario_atual)])


@router.get("", response_model=list[schemas.ServicoOut])
def listar(db: Session = Depends(get_db)):
    return db.query(models.Servico).order_by(models.Servico.nome).all()


@router.post("", response_model=schemas.ServicoOut, status_code=201)
def criar(payload: schemas.ServicoIn, db: Session = Depends(get_db)):
    obj = models.Servico(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{servico_id}", response_model=schemas.ServicoOut)
def atualizar(servico_id: uuid.UUID, payload: schemas.ServicoIn, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Servico, servico_id, "Serviço")
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{servico_id}", status_code=204)
def excluir(servico_id: uuid.UUID, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Servico, servico_id, "Serviço")
    db.delete(obj)
    db.commit()
