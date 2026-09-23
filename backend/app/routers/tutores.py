import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_usuario_atual, require_admin
from ..database import get_db
from ..utils import get_or_404, registrar_auditoria

router = APIRouter(prefix="/api/tutores", tags=["tutores"], dependencies=[Depends(get_usuario_atual)])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=list[schemas.TutorOut])
def listar(busca: str = "", db: Session = Depends(get_db)):
    q = db.query(models.Tutor)
    if busca:
        like = f"%{busca}%"
        q = q.filter(or_(models.Tutor.nome.ilike(like), models.Tutor.tel.ilike(like)))
    return q.order_by(models.Tutor.criado_em.desc()).all()


@router.post("", response_model=schemas.TutorOut, status_code=201)
def criar(
    payload: schemas.TutorIn,
    request: Request,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_atual),
):
    dados = payload.model_dump()
    if dados["consentimento_dados"]:
        dados["consentimento_em"] = dt.datetime.now(dt.timezone.utc)
    obj = models.Tutor(**dados)
    db.add(obj)
    db.flush()
    registrar_auditoria(db, usuario, "criar", "tutor", obj.id, ip=_ip(request))
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{tutor_id}", response_model=schemas.TutorOut)
def obter(tutor_id: uuid.UUID, db: Session = Depends(get_db)):
    return get_or_404(db, models.Tutor, tutor_id, "Tutor")


@router.put("/{tutor_id}", response_model=schemas.TutorOut)
def atualizar(
    tutor_id: uuid.UUID,
    payload: schemas.TutorIn,
    request: Request,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_atual),
):
    obj = get_or_404(db, models.Tutor, tutor_id, "Tutor")
    dados = payload.model_dump()
    if dados["consentimento_dados"] and not obj.consentimento_em:
        dados["consentimento_em"] = dt.datetime.now(dt.timezone.utc)
    elif not dados["consentimento_dados"]:
        dados["consentimento_em"] = None
    else:
        dados["consentimento_em"] = obj.consentimento_em
    for k, v in dados.items():
        setattr(obj, k, v)
    registrar_auditoria(db, usuario, "atualizar", "tutor", obj.id, ip=_ip(request))
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{tutor_id}", status_code=204)
def excluir(
    tutor_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_atual),
):
    obj = get_or_404(db, models.Tutor, tutor_id, "Tutor")
    registrar_auditoria(db, usuario, "excluir", "tutor", obj.id, detalhe=obj.nome, ip=_ip(request))
    db.delete(obj)
    db.commit()


@router.get("/{tutor_id}/pacientes", response_model=list[schemas.PacienteOut])
def pacientes_do_tutor(tutor_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.query(models.Paciente).filter(models.Paciente.tutor_id == tutor_id).all()


@router.get("/{tutor_id}/exportar", dependencies=[Depends(require_admin)])
def exportar_dados(
    tutor_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_atual),
):
    """Direito de acesso/portabilidade (LGPD art. 9º/18) — exporta os dados do titular."""
    tutor = get_or_404(db, models.Tutor, tutor_id, "Tutor")
    pacientes = db.query(models.Paciente).filter(models.Paciente.tutor_id == tutor_id).all()
    registrar_auditoria(db, usuario, "exportar", "tutor", tutor.id, ip=_ip(request))
    db.commit()
    return {
        "tutor": schemas.TutorOut.model_validate(tutor).model_dump(mode="json"),
        "pacientes": [
            {
                "id": str(p.id),
                "nome": p.nome,
                "especie": p.especie,
                "raca": p.raca,
                "peso": float(p.peso) if p.peso is not None else None,
                "data_nascimento": p.data_nascimento.isoformat() if p.data_nascimento else None,
                "obs": p.obs,
                "criado_em": p.criado_em.isoformat(),
            }
            for p in pacientes
        ],
        "gerado_em": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
