import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import hash_senha, require_admin
from ..database import get_db
from ..utils import get_or_404

router = APIRouter(prefix="/api/usuarios", tags=["usuarios"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[schemas.UsuarioOut])
def listar(db: Session = Depends(get_db)):
    return db.query(models.Usuario).order_by(models.Usuario.nome).all()


@router.post("", response_model=schemas.UsuarioOut, status_code=201)
def criar(payload: schemas.UsuarioIn, db: Session = Depends(get_db)):
    existente = db.query(models.Usuario).filter(models.Usuario.email == payload.email.strip().lower()).first()
    if existente:
        raise HTTPException(status_code=400, detail="Já existe um usuário com esse e-mail.")
    obj = models.Usuario(
        nome=payload.nome,
        email=payload.email.strip().lower(),
        papel=payload.papel,
        senha_hash=hash_senha(payload.senha),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{id}", response_model=schemas.UsuarioOut)
def atualizar(id: uuid.UUID, payload: schemas.UsuarioUpdateIn, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Usuario, id, "Usuário")
    if payload.nome is not None:
        obj.nome = payload.nome
    if payload.papel is not None:
        obj.papel = payload.papel
    if payload.ativo is not None:
        obj.ativo = payload.ativo
    if payload.senha:
        obj.senha_hash = hash_senha(payload.senha)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}", status_code=204)
def excluir(id: uuid.UUID, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Usuario, id, "Usuário")
    db.delete(obj)
    db.commit()
