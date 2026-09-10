import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_usuario_atual
from ..database import get_db
from ..utils import debitar_estoque, get_or_404, montar_insumos, valor_por_peso

router = APIRouter(tags=["cirurgias"], dependencies=[Depends(get_usuario_atual)])


@router.get("/api/pacientes/{paciente_id}/cirurgias", response_model=list[schemas.CirurgiaOut])
def listar(paciente_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(models.CirurgiaHist)
        .filter(models.CirurgiaHist.paciente_id == paciente_id)
        .order_by(models.CirurgiaHist.criado_em.desc())
        .all()
    )


@router.post("/api/pacientes/{paciente_id}/cirurgias", response_model=schemas.CirurgiaOut, status_code=201)
def criar(paciente_id: uuid.UUID, payload: schemas.CirurgiaIn, db: Session = Depends(get_db)):
    paciente = get_or_404(db, models.Paciente, paciente_id, "Paciente")
    peso = float(paciente.peso or 0)

    procedimentos = []
    total_proc = 0.0
    for cat_id in payload.cirurgia_cat_ids:
        cat = get_or_404(db, models.CirurgiaCategoria, cat_id, "Procedimento")
        v = valor_por_peso(cat, peso)
        procedimentos.append({"id": str(cat.id), "nome": cat.nome, "valor": v})
        total_proc += v

    insumos, total_ins, debitos = montar_insumos(db, payload.insumos)

    total = total_proc + total_ins
    servicos_cobranca = list(procedimentos)
    if payload.plantao and total_proc > 0:
        acrescimo = total_proc * 0.5
        total += acrescimo
        servicos_cobranca.append({"id": str(uuid.uuid4()), "nome": "🌙 Plantão (+50%)", "valor": acrescimo})
    if payload.outra_cidade:
        total += 50
        servicos_cobranca.append({"id": str(uuid.uuid4()), "nome": "📍 Deslocamento (outra cidade)", "valor": 50})

    data = payload.model_dump(exclude={"cirurgia_cat_ids", "insumos", "data", "hora"})
    obj = models.CirurgiaHist(
        paciente_id=paciente_id,
        **data,
        procedimentos=procedimentos,
        insumos=insumos,
        total=total,
        **({"data": payload.data} if payload.data else {}),
        **({"hora": payload.hora} if payload.hora else {}),
    )
    db.add(obj)

    if procedimentos or insumos:
        debitar_estoque(debitos)
        cobranca = models.Cobranca(
            paciente_id=paciente_id,
            servicos=servicos_cobranca,
            insumos=insumos,
            obs=f"Cirurgia: {payload.proc}",
            total=total,
            status="pendente",
            tutor_nome=paciente.tutor.nome if paciente.tutor else "",
        )
        db.add(cobranca)

    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/api/cirurgias/{id}", status_code=204)
def excluir(id: uuid.UUID, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.CirurgiaHist, id, "Registro cirúrgico")
    db.delete(obj)
    db.commit()
