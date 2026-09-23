import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_usuario_atual
from ..database import get_db
from ..utils import get_or_404, registrar_auditoria, validar_tamanho_base64

router = APIRouter(prefix="/api/pacientes", tags=["pacientes"], dependencies=[Depends(get_usuario_atual)])

MAX_FOTO_PERFIL_BYTES = 3 * 1024 * 1024


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=list[schemas.PacienteOut])
def listar(busca: str = "", db: Session = Depends(get_db)):
    q = db.query(models.Paciente).outerjoin(models.Tutor)
    if busca:
        like = f"%{busca}%"
        q = q.filter(or_(models.Paciente.nome.ilike(like), models.Tutor.nome.ilike(like)))
    return q.order_by(models.Paciente.criado_em.desc()).all()


@router.post("", response_model=schemas.PacienteOut, status_code=201)
def criar(
    payload: schemas.PacienteIn,
    request: Request,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_atual),
):
    validar_tamanho_base64(payload.foto_perfil, MAX_FOTO_PERFIL_BYTES, "A foto de perfil")
    obj = models.Paciente(**payload.model_dump())
    db.add(obj)
    db.flush()
    registrar_auditoria(db, usuario, "criar", "paciente", obj.id, ip=_ip(request))
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{id}", response_model=schemas.PacienteOut)
def obter(id: uuid.UUID, db: Session = Depends(get_db)):
    return get_or_404(db, models.Paciente, id, "Paciente")


@router.put("/{id}", response_model=schemas.PacienteOut)
def atualizar(
    id: uuid.UUID,
    payload: schemas.PacienteIn,
    request: Request,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_atual),
):
    validar_tamanho_base64(payload.foto_perfil, MAX_FOTO_PERFIL_BYTES, "A foto de perfil")
    obj = get_or_404(db, models.Paciente, id, "Paciente")
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    registrar_auditoria(db, usuario, "atualizar", "paciente", obj.id, ip=_ip(request))
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}", status_code=204)
def excluir(
    id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_atual),
):
    obj = get_or_404(db, models.Paciente, id, "Paciente")
    registrar_auditoria(db, usuario, "excluir", "paciente", obj.id, detalhe=obj.nome, ip=_ip(request))
    db.delete(obj)
    db.commit()


@router.put("/{id}/foto", response_model=schemas.PacienteOut)
def atualizar_foto(id: uuid.UUID, payload: dict, db: Session = Depends(get_db)):
    validar_tamanho_base64(payload.get("foto_perfil"), MAX_FOTO_PERFIL_BYTES, "A foto de perfil")
    obj = get_or_404(db, models.Paciente, id, "Paciente")
    obj.foto_perfil = payload.get("foto_perfil")
    db.commit()
    db.refresh(obj)
    return obj
