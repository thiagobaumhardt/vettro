import base64
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_usuario_atual
from ..database import get_db
from ..utils import get_or_404

router = APIRouter(tags=["exames"], dependencies=[Depends(get_usuario_atual)])

MAX_BYTES = 5 * 1024 * 1024


@router.get("/api/pacientes/{paciente_id}/exames", response_model=list[schemas.ExameOut])
def listar(paciente_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(models.Exame)
        .filter(models.Exame.paciente_id == paciente_id)
        .order_by(models.Exame.criado_em.desc())
        .all()
    )


@router.post("/api/pacientes/{paciente_id}/exames", response_model=list[schemas.ExameOut], status_code=201)
async def anexar(paciente_id: uuid.UUID, files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    get_or_404(db, models.Paciente, paciente_id, "Paciente")
    criados = []
    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f'"{file.filename}" não é PDF.')
        conteudo = await file.read()
        if len(conteudo) > MAX_BYTES:
            raise HTTPException(status_code=400, detail=f'"{file.filename}" excede 5 MB.')
        b64 = f"data:application/pdf;base64,{base64.b64encode(conteudo).decode()}"
        obj = models.Exame(paciente_id=paciente_id, nome=file.filename, tamanho=len(conteudo), conteudo=b64)
        db.add(obj)
        criados.append(obj)
    db.commit()
    for obj in criados:
        db.refresh(obj)
    return criados


@router.delete("/api/exames/{id}", status_code=204)
def excluir(id: uuid.UUID, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Exame, id, "Exame")
    db.delete(obj)
    db.commit()
