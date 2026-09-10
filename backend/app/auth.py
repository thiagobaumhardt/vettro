import datetime as dt
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

ALGORITHM = "HS256"


def hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return pwd_context.verify(senha, senha_hash)


def criar_token(usuario: "models.Usuario") -> str:
    expira = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=settings.jwt_expira_horas)
    payload = {"sub": str(usuario.id), "papel": usuario.papel, "exp": expira}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def get_usuario_atual(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> "models.Usuario":
    credenciais_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sessão inválida ou expirada.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credenciais_invalidas
    except JWTError:
        raise credenciais_invalidas

    usuario = db.get(models.Usuario, uuid.UUID(user_id))
    if usuario is None or not usuario.ativo:
        raise credenciais_invalidas
    return usuario


def require_admin(usuario: "models.Usuario" = Depends(get_usuario_atual)) -> "models.Usuario":
    if usuario.papel != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito ao administrador da clínica.",
        )
    return usuario
