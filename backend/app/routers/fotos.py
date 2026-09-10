import base64
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_usuario_atual
from ..database import get_db
from ..utils import get_or_404

router = APIRouter(tags=["fotos"], dependencies=[Depends(get_usuario_atual)])

MAX_BYTES = 4 * 1024 * 1024


@router.get("/api/pacientes/{paciente_id}/fotos", response_model=list[schemas.FotoOut])
def listar(paciente_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(models.Foto)
        .filter(models.Foto.paciente_id == paciente_id)
        .order_by(models.Foto.criado_em.desc())
        .all()
    )


@router.post("/api/pacientes/{paciente_id}/fotos", response_model=list[schemas.FotoOut], status_code=201)
async def anexar(paciente_id: uuid.UUID, files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    get_or_404(db, models.Paciente, paciente_id, "Paciente")
    criados = []
    for file in files:
        if not (file.content_type or "").startswith("image/"):
            continue
        conteudo = await file.read()
        if len(conteudo) > MAX_BYTES:
            raise HTTPException(status_code=400, detail=f'"{file.filename}" excede 4 MB.')
        b64 = f"data:{file.content_type};base64,{base64.b64encode(conteudo).decode()}"
        obj = models.Foto(paciente_id=paciente_id, nome=file.filename, conteudo=b64)
        db.add(obj)
        criados.append(obj)
    db.commit()
    for obj in criados:
        db.refresh(obj)
    return criados


@router.delete("/api/fotos/{id}", status_code=204)
def excluir(id: uuid.UUID, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Foto, id, "Foto")
    db.delete(obj)
    db.commit()
