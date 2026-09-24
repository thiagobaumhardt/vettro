import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django_tenants.models import DomainMixin, TenantMixin

from .managers import UsuarioManager


class Clinica(TenantMixin):
    """O tenant em si — 1 clínica = 1 schema Postgres (ver §3/§4 do plano)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=200)
    plano = models.CharField(max_length=30, default="padrao")
    ativa = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    # Criação/migração de schema é feita explicitamente pelo fluxo de
    # provisionamento (apps.plataforma.services.provisionar_clinica), não
    # como side-effect automático de save().
    auto_create_schema = False
    auto_drop_schema = False

    def __str__(self):
        return self.nome


class Dominio(DomainMixin):
    """Exigido pelo django-tenants mesmo sem roteamento por subdomínio real —
    toda Clinica aponta pro mesmo www.vettro.com.br. A resolução de qual
    clínica está ativa é feita por sessão (TenantFromSessionMiddleware), não
    pelo host da requisição. Ver §4 do plano."""


class Usuario(AbstractBaseUser, PermissionsMixin):
    """Identidade GLOBAL (schema public) — uma pessoa real, independente de
    quantas clínicas ela acessa. O papel (admin/vet) é por clínica, vive em
    UsuarioClinica, não aqui."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    nome = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)
    is_platform_admin = models.BooleanField(
        default=False,
        help_text="Administra a plataforma (provisiona clínicas) — não é o mesmo que admin de uma clínica.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nome"]

    class Meta:
        ordering = ["nome"]

    @property
    def is_staff(self):
        return self.is_platform_admin

    def __str__(self):
        return f"{self.nome} <{self.email}>"


class UsuarioClinica(models.Model):
    """Vínculo + papel por clínica. Uma mesma pessoa pode ter uma linha aqui
    por clínica que atende (ex: admin na própria, vet colaboradora em outra).

    Papéis pré-definidos, equivalentes aos "perfis modelo" do SimplesVet
    (veterinário/recepcionista/gestor) — não é um construtor de permissão
    livre, é um conjunto fixo de perfis (§9-bis do plano). O escopo de cada
    um vive em apps.core.decorators.PERMISSOES_POR_PAPEL, não aqui."""

    PAPEL_ADMIN = "admin"
    PAPEL_VET = "vet"
    PAPEL_ATENDENTE = "atendente"
    PAPEL_MOTORISTA = "motorista"
    PAPEL_CHOICES = [
        (PAPEL_ADMIN, "Admin"),
        (PAPEL_VET, "Veterinária/o"),
        (PAPEL_ATENDENTE, "Atendente administrativo"),
        (PAPEL_MOTORISTA, "Motorista"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="vinculos")
    clinica = models.ForeignKey(Clinica, on_delete=models.CASCADE, related_name="usuarios")
    papel = models.CharField(max_length=10, choices=PAPEL_CHOICES, default=PAPEL_VET)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["usuario", "clinica"], name="uniq_usuario_clinica"),
        ]

    def __str__(self):
        return f"{self.usuario.email} @ {self.clinica.schema_name} ({self.papel})"


class LoginAudit(models.Model):
    """Log de tentativas de login (schema public) — decisão tomada durante a
    implementação: o AuditLog "de verdade" (criar/atualizar/excluir) vive no
    schema de cada clínica (apps.auditoria), mas login acontece ANTES de
    qualquer clínica ser escolhida (schema public ativo), então uma
    tentativa de login — principalmente as que falham — não tem uma clínica
    pra pertencer ainda. Fica registrado aqui, globalmente; o acesso
    bem-sucedido a uma clínica específica gera um AuditLog próprio dentro
    daquele schema no momento em que a sessão ativa o schema (ver
    apps.contas.views._ativar_clinica)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email_tentado = models.EmailField()
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    sucesso = models.BooleanField()
    ip = models.CharField(max_length=45, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.email_tentado} {'OK' if self.sucesso else 'FALHA'} {self.criado_em:%d/%m/%Y %H:%M}"
