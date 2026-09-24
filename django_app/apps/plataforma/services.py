"""Provisionamento de clínicas novas — usado pela área de admin de
plataforma (substitui o backend/app/seed.py do sistema FastAPI atual, que
semeava um único admin fixo por deploy)."""
from django.core.management import call_command
from django.db import transaction

from .convites import enviar_convite
from .models import Clinica, Dominio, Usuario, UsuarioClinica

# O django-tenants exige um TENANT_DOMAIN_MODEL com `domain` único por
# tenant — mas nossa arquitetura não roteia por domínio (§4 do plano: domínio
# único www.vettro.com.br pra todas as clínicas, resolução por sessão). Cada
# Clinica recebe aqui um domínio SINTÉTICO só pra satisfazer essa exigência
# interna da biblioteca (usado por comandos de management como
# migrate_schemas/tenant_command); nunca é usado pra resolver requisições de
# verdade — isso é 100% feito por TenantFromSessionMiddleware.
DOMINIO_REAL = "www.vettro.com.br"


def provisionar_clinica(
    *, nome: str, schema_name: str, admin_email: str, admin_nome: str, admin_senha: str | None = None
) -> Clinica:
    """`admin_senha=None` (padrão, usado pela tela de admin de plataforma) —
    cria o admin SEM senha (set_unusable_password) e manda convite por
    e-mail pra ele definir a própria senha, mesmo padrão usado ao adicionar
    alguém em 🔑 Usuários (§5 do plano). Passar `admin_senha` diretamente
    continua disponível pra scripts/seed automatizados (sem e-mail)."""
    with transaction.atomic():
        clinica = Clinica.objects.create(nome=nome, schema_name=schema_name)
        Dominio.objects.create(
            domain=f"{schema_name}.{DOMINIO_REAL}", tenant=clinica, is_primary=True
        )

    # auto_create_schema=False (provisionamento é explícito, não side-effect
    # de save() — ver models.py) — então o schema Postgres precisa ser criado
    # manualmente aqui antes de rodar as migrations de tenant nele.
    clinica.create_schema(check_if_exists=True, verbosity=0)
    call_command("migrate_schemas", schema_name=schema_name, interactive=False, verbosity=0)

    email_normalizado = admin_email.strip().lower()
    usuario, criado = Usuario.objects.get_or_create(
        email=email_normalizado,
        defaults={"nome": admin_nome},
    )
    if criado:
        if admin_senha:
            usuario.set_password(admin_senha)
        else:
            usuario.set_unusable_password()
        usuario.save(update_fields=["password"])
        if not admin_senha:
            enviar_convite(usuario, nome)

    UsuarioClinica.objects.get_or_create(
        usuario=usuario, clinica=clinica, defaults={"papel": UsuarioClinica.PAPEL_ADMIN}
    )
    return clinica
