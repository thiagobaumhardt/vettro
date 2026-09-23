from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import require_admin
from ..database import get_db

router = APIRouter(prefix="/api/auditoria", tags=["auditoria"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[schemas.AuditLogOut])
def listar(entidade: str = "", limite: int = 200, db: Session = Depends(get_db)):
    q = db.query(models.AuditLog)
    if entidade:
        q = q.filter(models.AuditLog.entidade == entidade)
    return q.order_by(models.AuditLog.criado_em.desc()).limit(min(limite, 500)).all()
