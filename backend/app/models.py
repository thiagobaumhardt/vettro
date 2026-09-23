import datetime as dt
import uuid

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def uuid_pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Tutor(Base):
    __tablename__ = "tutores"

    id: Mapped[uuid.UUID] = uuid_pk()
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    tel: Mapped[str] = mapped_column(String(40), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200))
    cpf: Mapped[str | None] = mapped_column(String(20))
    cep: Mapped[str | None] = mapped_column(String(9))
    endereco: Mapped[str | None] = mapped_column(String(200))
    numero: Mapped[str | None] = mapped_column(String(20))
    complemento: Mapped[str | None] = mapped_column(String(100))
    bairro: Mapped[str | None] = mapped_column(String(100))
    cidade: Mapped[str | None] = mapped_column(String(100))
    uf: Mapped[str | None] = mapped_column(String(2))
    como_conheceu: Mapped[str | None] = mapped_column(String(30))
    obs: Mapped[str | None] = mapped_column(Text)
    consentimento_dados: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consentimento_em: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    pacientes: Mapped[list["Paciente"]] = relationship(back_populates="tutor")


class Paciente(Base):
    __tablename__ = "pacientes"

    id: Mapped[uuid.UUID] = uuid_pk()
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    especie: Mapped[str] = mapped_column(String(50), nullable=False)
    raca: Mapped[str | None] = mapped_column(String(120))
    peso: Mapped[float | None] = mapped_column(Numeric(6, 2))
    data_nascimento: Mapped[dt.date | None] = mapped_column(Date)
    obs: Mapped[str | None] = mapped_column(Text)
    foto_perfil: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Nullable at the DB level so excluir um tutor não apaga os pacientes vinculados
    # (eles ficam "sem tutor", igual ao comportamento original em localStorage).
    tutor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tutores.id", ondelete="SET NULL"))
    tutor: Mapped["Tutor | None"] = relationship(back_populates="pacientes")

    anamneses: Mapped[list["AnamneseHist"]] = relationship(back_populates="paciente", cascade="all, delete-orphan")
    cirurgias: Mapped[list["CirurgiaHist"]] = relationship(back_populates="paciente", cascade="all, delete-orphan")
    notas: Mapped[list["Nota"]] = relationship(back_populates="paciente", cascade="all, delete-orphan")
    exames: Mapped[list["Exame"]] = relationship(back_populates="paciente", cascade="all, delete-orphan")
    fotos: Mapped[list["Foto"]] = relationship(back_populates="paciente", cascade="all, delete-orphan")
    cobrancas: Mapped[list["Cobranca"]] = relationship(back_populates="paciente", cascade="all, delete-orphan")


class Servico(Base):
    __tablename__ = "servicos"

    id: Mapped[uuid.UUID] = uuid_pk()
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    valor: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)


class CirurgiaCategoria(Base):
    __tablename__ = "cirurgias_cat"

    id: Mapped[uuid.UUID] = uuid_pk()
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    valor_p: Mapped[float | None] = mapped_column(Numeric(10, 2))
    valor_m: Mapped[float | None] = mapped_column(Numeric(10, 2))
    valor_g: Mapped[float | None] = mapped_column(Numeric(10, 2))
    descricao: Mapped[str | None] = mapped_column(Text)


class Insumo(Base):
    __tablename__ = "insumos"

    id: Mapped[uuid.UUID] = uuid_pk()
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    categoria: Mapped[str | None] = mapped_column(String(80))
    valor: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    qtd: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    codigo_barras: Mapped[str | None] = mapped_column(String(64), unique=True)
    unidades_por_pacote: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    data_validade: Mapped[dt.date | None] = mapped_column(Date)
    lote: Mapped[str | None] = mapped_column(String(60))
    obs: Mapped[str | None] = mapped_column(Text)


class AnamneseHist(Base):
    __tablename__ = "anamnese_hist"

    id: Mapped[uuid.UUID] = uuid_pk()
    paciente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False)
    paciente: Mapped["Paciente"] = relationship(back_populates="anamneses")

    data: Mapped[dt.date] = mapped_column(Date, server_default=func.current_date())
    hora: Mapped[dt.time] = mapped_column(Time, server_default=func.current_time())

    queixa: Mapped[str | None] = mapped_column(Text)
    historico: Mapped[str | None] = mapped_column(Text)
    medicamentos: Mapped[str | None] = mapped_column(Text)
    alergias: Mapped[str | None] = mapped_column(String(300))
    obs_add: Mapped[str | None] = mapped_column(Text)
    alimentacao: Mapped[str | None] = mapped_column(String(60))
    vacina: Mapped[str | None] = mapped_column(String(30))
    verme: Mapped[str | None] = mapped_column(String(30))
    rua: Mapped[str | None] = mapped_column(String(20))
    convive: Mapped[str | None] = mapped_column(String(10))

    av_fc: Mapped[str | None] = mapped_column(String(20))
    av_fr: Mapped[str | None] = mapped_column(String(20))
    av_pa: Mapped[str | None] = mapped_column(String(20))
    av_temp: Mapped[str | None] = mapped_column(String(20))
    av_hidratacao: Mapped[str | None] = mapped_column(String(60))
    av_mucosas: Mapped[str | None] = mapped_column(String(60))
    av_linf_sub: Mapped[str | None] = mapped_column(String(60))
    av_linf_sube: Mapped[str | None] = mapped_column(String(60))
    av_linf_ing: Mapped[str | None] = mapped_column(String(60))
    av_linf_pop: Mapped[str | None] = mapped_column(String(60))
    av_demais: Mapped[str | None] = mapped_column(Text)

    servicos: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    insumos: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    plantao: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CirurgiaHist(Base):
    __tablename__ = "cirurgias_hist"

    id: Mapped[uuid.UUID] = uuid_pk()
    paciente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False)
    paciente: Mapped["Paciente"] = relationship(back_populates="cirurgias")

    data: Mapped[dt.date] = mapped_column(Date, server_default=func.current_date())
    hora: Mapped[dt.time] = mapped_column(Time, server_default=func.current_time())

    proc: Mapped[str] = mapped_column(String(200), nullable=False)
    clinica: Mapped[str | None] = mapped_column(String(200))
    anestesista: Mapped[str | None] = mapped_column(String(200))
    procedimentos: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    insumos: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    plantao: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    outra_cidade: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    desc_cir: Mapped[str | None] = mapped_column(Text)
    pos_op: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Nota(Base):
    __tablename__ = "notas"

    id: Mapped[uuid.UUID] = uuid_pk()
    paciente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False)
    paciente: Mapped["Paciente"] = relationship(back_populates="notas")

    titulo: Mapped[str | None] = mapped_column(String(200))
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    editado_em: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class Exame(Base):
    __tablename__ = "exames"

    id: Mapped[uuid.UUID] = uuid_pk()
    paciente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False)
    paciente: Mapped["Paciente"] = relationship(back_populates="exames")

    nome: Mapped[str] = mapped_column(String(300), nullable=False)
    tamanho: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Foto(Base):
    __tablename__ = "fotos"

    id: Mapped[uuid.UUID] = uuid_pk()
    paciente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False)
    paciente: Mapped["Paciente"] = relationship(back_populates="fotos")

    nome: Mapped[str] = mapped_column(String(300), nullable=False)
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Cobranca(Base):
    __tablename__ = "cobrancas"

    id: Mapped[uuid.UUID] = uuid_pk()
    paciente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False)
    paciente: Mapped["Paciente"] = relationship(back_populates="cobrancas")

    servicos: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    insumos: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    obs: Mapped[str | None] = mapped_column(Text)
    total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pendente")
    tutor_nome: Mapped[str | None] = mapped_column(String(200))
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Atendimento(Base):
    """Módulo 'Atendimentos' (independente da ficha do paciente)."""

    __tablename__ = "atendimentos"

    id: Mapped[uuid.UUID] = uuid_pk()
    paciente_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("pacientes.id", ondelete="SET NULL"))
    pac_nome: Mapped[str] = mapped_column(String(200), nullable=False)
    pac_especie: Mapped[str | None] = mapped_column(String(50))
    tutor_nome: Mapped[str | None] = mapped_column(String(200))
    tutor_tel: Mapped[str | None] = mapped_column(String(40))

    data: Mapped[dt.date] = mapped_column(Date, nullable=False)
    hora: Mapped[dt.time | None] = mapped_column(Time)
    servicos: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    insumos: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    plantao: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    obs: Mapped[str | None] = mapped_column(Text)
    total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = uuid_pk()
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    senha_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    papel: Mapped[str] = mapped_column(String(20), nullable=False, default="vet")  # 'admin' | 'vet'
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Agendamento(Base):
    __tablename__ = "agendamentos"

    id: Mapped[uuid.UUID] = uuid_pk()
    paciente_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("pacientes.id", ondelete="SET NULL"))
    data: Mapped[dt.date] = mapped_column(Date, nullable=False)
    hora: Mapped[dt.time | None] = mapped_column(Time)
    pac_nome: Mapped[str] = mapped_column(String(200), nullable=False)
    tutor_nome: Mapped[str | None] = mapped_column(String(200))
    tutor_tel: Mapped[str | None] = mapped_column(String(40))
    queixa: Mapped[str | None] = mapped_column(Text)
    servicos: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    servicos_livre: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="agendado")
    obs: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    """Trilha de auditoria (rastreabilidade exigida pelo princípio de responsabilização da LGPD)."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = uuid_pk()
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    usuario_nome: Mapped[str | None] = mapped_column(String(200))
    acao: Mapped[str] = mapped_column(String(30), nullable=False)  # login_ok | login_falha | criar | atualizar | excluir | exportar
    entidade: Mapped[str] = mapped_column(String(30), nullable=False)  # tutor | paciente | usuario | auth
    entidade_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    detalhe: Mapped[str | None] = mapped_column(String(300))
    ip: Mapped[str | None] = mapped_column(String(45))
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
