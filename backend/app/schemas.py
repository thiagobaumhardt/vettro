import datetime as dt
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from .utils import cpf_valido


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Tutor ──
class TutorIn(BaseModel):
    nome: str
    tel: str
    email: Optional[str] = None
    cpf: Optional[str] = None
    cep: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    cidade: Optional[str] = None
    uf: Optional[str] = None
    como_conheceu: Optional[str] = None
    obs: Optional[str] = None
    consentimento_dados: bool = False

    @field_validator("cpf")
    @classmethod
    def _valida_cpf(cls, v):
        if v and not cpf_valido(v):
            raise ValueError("CPF inválido.")
        return v


class TutorOut(ORMModel):
    id: uuid.UUID
    nome: str
    tel: str
    email: Optional[str] = None
    cpf: Optional[str] = None
    cep: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    cidade: Optional[str] = None
    uf: Optional[str] = None
    como_conheceu: Optional[str] = None
    obs: Optional[str] = None
    consentimento_dados: bool = False
    consentimento_em: Optional[dt.datetime] = None
    criado_em: dt.datetime


# ── Paciente ──
class TutorResumo(ORMModel):
    id: uuid.UUID
    nome: str
    tel: str


class PacienteIn(BaseModel):
    nome: str
    especie: str
    raca: Optional[str] = None
    peso: Optional[float] = None
    data_nascimento: Optional[dt.date] = None
    tutor_id: uuid.UUID
    obs: Optional[str] = None
    foto_perfil: Optional[str] = None


class PacienteOut(ORMModel):
    id: uuid.UUID
    nome: str
    especie: str
    raca: Optional[str] = None
    peso: Optional[float] = None
    data_nascimento: Optional[dt.date] = None
    tutor_id: uuid.UUID
    obs: Optional[str] = None
    foto_perfil: Optional[str] = None
    criado_em: dt.datetime
    tutor: Optional[TutorResumo] = None


# ── Servico ──
class ServicoIn(BaseModel):
    nome: str
    valor: float
    descricao: Optional[str] = None


class ServicoOut(ORMModel):
    id: uuid.UUID
    nome: str
    valor: float
    descricao: Optional[str] = None


# ── Procedimento cirúrgico (catálogo) ──
class CirurgiaCategoriaIn(BaseModel):
    nome: str
    valor_p: Optional[float] = None
    valor_m: Optional[float] = None
    valor_g: Optional[float] = None
    descricao: Optional[str] = None


class CirurgiaCategoriaOut(ORMModel):
    id: uuid.UUID
    nome: str
    valor_p: Optional[float] = None
    valor_m: Optional[float] = None
    valor_g: Optional[float] = None
    descricao: Optional[str] = None


# ── Insumo ──
class InsumoIn(BaseModel):
    nome: str
    categoria: Optional[str] = None
    valor: float
    qtd: int = 0
    codigo_barras: Optional[str] = None
    unidades_por_pacote: int = 1
    data_validade: Optional[dt.date] = None
    lote: Optional[str] = None
    obs: Optional[str] = None


class InsumoOut(ORMModel):
    id: uuid.UUID
    nome: str
    categoria: Optional[str] = None
    valor: float
    qtd: int
    codigo_barras: Optional[str] = None
    unidades_por_pacote: int
    data_validade: Optional[dt.date] = None
    lote: Optional[str] = None
    obs: Optional[str] = None


class ReporIn(BaseModel):
    qtd: int


# ── Itens de uso (serviço/insumo com quantidade) ──
class InsumoUso(BaseModel):
    id: uuid.UUID
    qtd: int = 1


# ── Anamnese (atendimento na ficha do paciente) ──
class AnamneseIn(BaseModel):
    queixa: Optional[str] = None
    historico: Optional[str] = None
    medicamentos: Optional[str] = None
    alergias: Optional[str] = None
    obs_add: Optional[str] = None
    alimentacao: Optional[str] = None
    vacina: Optional[str] = None
    verme: Optional[str] = None
    rua: Optional[str] = None
    convive: Optional[str] = None
    av_fc: Optional[str] = None
    av_fr: Optional[str] = None
    av_pa: Optional[str] = None
    av_temp: Optional[str] = None
    av_hidratacao: Optional[str] = None
    av_mucosas: Optional[str] = None
    av_linf_sub: Optional[str] = None
    av_linf_sube: Optional[str] = None
    av_linf_ing: Optional[str] = None
    av_linf_pop: Optional[str] = None
    av_demais: Optional[str] = None
    servico_ids: list[uuid.UUID] = []
    insumos: list[InsumoUso] = []
    plantao: bool = False


class AnamneseOut(ORMModel):
    id: uuid.UUID
    paciente_id: uuid.UUID
    data: dt.date
    hora: dt.time
    queixa: Optional[str] = None
    historico: Optional[str] = None
    medicamentos: Optional[str] = None
    alergias: Optional[str] = None
    obs_add: Optional[str] = None
    alimentacao: Optional[str] = None
    vacina: Optional[str] = None
    verme: Optional[str] = None
    rua: Optional[str] = None
    convive: Optional[str] = None
    av_fc: Optional[str] = None
    av_fr: Optional[str] = None
    av_pa: Optional[str] = None
    av_temp: Optional[str] = None
    av_hidratacao: Optional[str] = None
    av_mucosas: Optional[str] = None
    av_linf_sub: Optional[str] = None
    av_linf_sube: Optional[str] = None
    av_linf_ing: Optional[str] = None
    av_linf_pop: Optional[str] = None
    av_demais: Optional[str] = None
    servicos: list[dict] = []
    insumos: list[dict] = []
    plantao: bool
    total: float


# ── Cirurgia (histórico do paciente) ──
class CirurgiaIn(BaseModel):
    proc: str
    clinica: Optional[str] = None
    anestesista: Optional[str] = None
    data: Optional[dt.date] = None
    hora: Optional[dt.time] = None
    cirurgia_cat_ids: list[uuid.UUID] = []
    insumos: list[InsumoUso] = []
    plantao: bool = False
    outra_cidade: bool = False
    desc_cir: Optional[str] = None
    pos_op: Optional[str] = None


class CirurgiaOut(ORMModel):
    id: uuid.UUID
    paciente_id: uuid.UUID
    data: dt.date
    hora: dt.time
    proc: str
    clinica: Optional[str] = None
    anestesista: Optional[str] = None
    procedimentos: list[dict] = []
    insumos: list[dict] = []
    total: float
    plantao: bool
    outra_cidade: bool
    desc_cir: Optional[str] = None
    pos_op: Optional[str] = None


# ── Nota ──
class NotaIn(BaseModel):
    titulo: Optional[str] = None
    conteudo: str


class NotaOut(ORMModel):
    id: uuid.UUID
    paciente_id: uuid.UUID
    titulo: Optional[str] = None
    conteudo: str
    criado_em: dt.datetime
    editado_em: Optional[dt.datetime] = None


# ── Exame / Foto ──
class ExameOut(ORMModel):
    id: uuid.UUID
    paciente_id: uuid.UUID
    nome: str
    tamanho: int
    conteudo: str
    criado_em: dt.datetime


class FotoOut(ORMModel):
    id: uuid.UUID
    paciente_id: uuid.UUID
    nome: str
    conteudo: str
    criado_em: dt.datetime


# ── Cobrança ──
class CobrancaIn(BaseModel):
    servico_ids: list[uuid.UUID] = []
    insumos: list[InsumoUso] = []
    obs: Optional[str] = None


class CobrancaOut(ORMModel):
    id: uuid.UUID
    paciente_id: uuid.UUID
    servicos: list[dict] = []
    insumos: list[dict] = []
    obs: Optional[str] = None
    total: float
    status: str
    tutor_nome: Optional[str] = None
    criado_em: dt.datetime


# ── Atendimento (módulo) ──
class AtendimentoIn(BaseModel):
    paciente_id: uuid.UUID
    data: dt.date
    hora: Optional[dt.time] = None
    servico_ids: list[uuid.UUID] = []
    insumos: list[InsumoUso] = []
    plantao: bool = False
    obs: Optional[str] = None


class AtendimentoOut(ORMModel):
    id: uuid.UUID
    paciente_id: Optional[uuid.UUID] = None
    pac_nome: str
    pac_especie: Optional[str] = None
    tutor_nome: Optional[str] = None
    tutor_tel: Optional[str] = None
    data: dt.date
    hora: Optional[dt.time] = None
    servicos: list[dict] = []
    insumos: list[dict] = []
    plantao: bool
    obs: Optional[str] = None
    total: float
    criado_em: dt.datetime


# ── Agendamento ──
class AgendamentoIn(BaseModel):
    data: dt.date
    hora: Optional[dt.time] = None
    paciente_id: Optional[uuid.UUID] = None
    pac_nome: str
    tutor_nome: Optional[str] = None
    tutor_tel: Optional[str] = None
    queixa: Optional[str] = None
    servico_ids: list[uuid.UUID] = []
    servicos_livre: Optional[str] = None
    status: str = "agendado"
    obs: Optional[str] = None


class AgendamentoOut(ORMModel):
    id: uuid.UUID
    paciente_id: Optional[uuid.UUID] = None
    data: dt.date
    hora: Optional[dt.time] = None
    pac_nome: str
    tutor_nome: Optional[str] = None
    tutor_tel: Optional[str] = None
    queixa: Optional[str] = None
    servicos: list[dict] = []
    servicos_livre: Optional[str] = None
    status: str
    obs: Optional[str] = None
    criado_em: dt.datetime


class AgendamentoStatusIn(BaseModel):
    status: str


class AgendamentoReagendarIn(BaseModel):
    data: dt.date
    hora: Optional[dt.time] = None


# ── Usuário / Auth ──
def _valida_forca_senha(v: str) -> str:
    if len(v) < 8:
        raise ValueError("A senha deve ter no mínimo 8 caracteres.")
    if v.isdigit() or v.isalpha():
        raise ValueError("A senha deve combinar letras e números.")
    return v


class UsuarioIn(BaseModel):
    nome: str
    email: str
    senha: str
    papel: str = "vet"  # 'admin' | 'vet'

    @field_validator("senha")
    @classmethod
    def _senha_forte(cls, v):
        return _valida_forca_senha(v)


class UsuarioUpdateIn(BaseModel):
    nome: Optional[str] = None
    papel: Optional[str] = None
    ativo: Optional[bool] = None
    senha: Optional[str] = None

    @field_validator("senha")
    @classmethod
    def _senha_forte(cls, v):
        return _valida_forca_senha(v) if v else v


class UsuarioOut(ORMModel):
    id: uuid.UUID
    nome: str
    email: str
    papel: str
    ativo: bool
    criado_em: dt.datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut


# ── Dashboard ──
class DashboardStats(BaseModel):
    tutores: int
    pacientes: int
    servicos: int
    insumos: int
    atendimentos: int
    agendados: int


class EstoqueAlerta(BaseModel):
    zerados: list[InsumoOut]
    baixos: list[InsumoOut]
    vencidos: list[InsumoOut] = []
    vencendo: list[InsumoOut] = []


# ── Importação de XML de NF-e (pedido de compra) ──
class ImportarXmlResultado(BaseModel):
    criados: list[InsumoOut] = []
    atualizados: list[InsumoOut] = []
    ignorados: list[str] = []


# ── Auditoria (LGPD — rastreabilidade) ──
class AuditLogOut(ORMModel):
    id: uuid.UUID
    usuario_nome: Optional[str] = None
    acao: str
    entidade: str
    entidade_id: Optional[uuid.UUID] = None
    detalhe: Optional[str] = None
    ip: Optional[str] = None
    criado_em: dt.datetime
