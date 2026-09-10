from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import criar_token, get_usuario_atual, verificar_senha
from ..database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=schemas.TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    usuario = (
        db.query(models.Usuario)
        .filter(func.lower(models.Usuario.email) == form.username.strip().lower())
        .first()
    )
    if not usuario or not usuario.ativo or not verificar_senha(form.password, usuario.senha_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.")
    return schemas.TokenOut(access_token=criar_token(usuario), usuario=usuario)


@router.get("/me", response_model=schemas.UsuarioOut)
def me(usuario: models.Usuario = Depends(get_usuario_atual)):
    return usuario
