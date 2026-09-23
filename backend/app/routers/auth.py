from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from .. import ratelimit
from ..auth import criar_token, get_usuario_atual, verificar_senha
from ..database import get_db
from ..utils import registrar_auditoria

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=schemas.TokenOut)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    ip = request.client.host if request.client else None
    chave = f"{ip}:{form.username.strip().lower()}"

    if ratelimit.bloqueado(chave):
        raise HTTPException(
            status_code=429,
            detail="Muitas tentativas de login. Aguarde alguns minutos antes de tentar novamente.",
        )

    usuario = (
        db.query(models.Usuario)
        .filter(func.lower(models.Usuario.email) == form.username.strip().lower())
        .first()
    )
    if not usuario or not usuario.ativo or not verificar_senha(form.password, usuario.senha_hash):
        ratelimit.registrar_falha(chave)
        registrar_auditoria(db, usuario, "login_falha", "auth", detalhe=form.username.strip().lower(), ip=ip)
        db.commit()
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.")

    ratelimit.limpar(chave)
    registrar_auditoria(db, usuario, "login_ok", "auth", entidade_id=usuario.id, ip=ip)
    db.commit()
    return schemas.TokenOut(access_token=criar_token(usuario), usuario=usuario)


@router.get("/me", response_model=schemas.UsuarioOut)
def me(usuario: models.Usuario = Depends(get_usuario_atual)):
    return usuario
