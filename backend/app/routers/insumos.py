import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_usuario_atual
from ..database import get_db
from ..nfe import parsear_nfe
from ..utils import get_or_404, registrar_auditoria

router = APIRouter(prefix="/api/insumos", tags=["insumos"], dependencies=[Depends(get_usuario_atual)])


def _valida_codigo_barras_unico(db: Session, codigo: str | None, ignorar_id: uuid.UUID | None = None):
    if not codigo:
        return
    q = db.query(models.Insumo).filter(models.Insumo.codigo_barras == codigo)
    if ignorar_id:
        q = q.filter(models.Insumo.id != ignorar_id)
    if q.first():
        raise HTTPException(status_code=400, detail="Já existe um insumo cadastrado com esse código de barras.")


@router.get("", response_model=list[schemas.InsumoOut])
def listar(db: Session = Depends(get_db)):
    return db.query(models.Insumo).order_by(models.Insumo.nome).all()


@router.get("/codigo/{codigo}", response_model=schemas.InsumoOut)
def obter_por_codigo(codigo: str, db: Session = Depends(get_db)):
    obj = db.query(models.Insumo).filter(models.Insumo.codigo_barras == codigo).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="Nenhum insumo cadastrado com esse código de barras.")
    return obj


@router.post("", response_model=schemas.InsumoOut, status_code=201)
def criar(payload: schemas.InsumoIn, db: Session = Depends(get_db)):
    _valida_codigo_barras_unico(db, payload.codigo_barras)
    obj = models.Insumo(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{id}", response_model=schemas.InsumoOut)
def atualizar(id: uuid.UUID, payload: schemas.InsumoIn, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Insumo, id, "Insumo")
    _valida_codigo_barras_unico(db, payload.codigo_barras, ignorar_id=id)
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}", status_code=204)
def excluir(id: uuid.UUID, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Insumo, id, "Insumo")
    db.delete(obj)
    db.commit()


@router.patch("/{id}/repor", response_model=schemas.InsumoOut)
def repor(id: uuid.UUID, payload: schemas.ReporIn, db: Session = Depends(get_db)):
    obj = get_or_404(db, models.Insumo, id, "Insumo")
    obj.qtd += payload.qtd
    db.commit()
    db.refresh(obj)
    return obj


@router.post("/importar-xml", response_model=schemas.ImportarXmlResultado)
async def importar_xml(
    request: Request,
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_atual),
):
    """Importa os itens de uma NF-e de compra: casa pelo código de barras (soma ao
    estoque existente) ou cadastra um insumo novo. Lote/validade vêm do bloco <rastro>
    da nota quando o fornecedor os informa (comum em medicamentos)."""
    conteudo = await arquivo.read()
    itens = parsear_nfe(conteudo)
    ip = request.client.host if request.client else None

    criados, atualizados, ignorados = [], [], []

    for item in itens:
        if item.quantidade <= 0:
            ignorados.append(f"{item.nome} (quantidade inválida na nota)")
            continue

        existente = (
            db.query(models.Insumo).filter(models.Insumo.codigo_barras == item.codigo_barras).first()
            if item.codigo_barras
            else None
        )

        if existente:
            existente.qtd += int(round(item.quantidade))
            if item.validade:
                existente.data_validade = item.validade
            if item.lote:
                existente.lote = item.lote
            registrar_auditoria(
                db, usuario, "atualizar", "insumo", existente.id, detalhe=f"+{item.quantidade} via XML NF-e", ip=ip
            )
            atualizados.append(existente)
        else:
            novo = models.Insumo(
                nome=item.nome,
                valor=item.valor_unitario,
                qtd=int(round(item.quantidade)),
                codigo_barras=item.codigo_barras,
                data_validade=item.validade,
                lote=item.lote,
                obs="Importado via XML de NF-e.",
            )
            db.add(novo)
            db.flush()
            registrar_auditoria(db, usuario, "criar", "insumo", novo.id, detalhe="Importado via XML NF-e", ip=ip)
            criados.append(novo)

    db.commit()
    for obj in criados + atualizados:
        db.refresh(obj)
    return schemas.ImportarXmlResultado(criados=criados, atualizados=atualizados, ignorados=ignorados)
