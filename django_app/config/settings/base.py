import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-secret-troque-em-producao")
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# --- django-tenants ---------------------------------------------------------
SHARED_APPS = [
    "django_tenants",
    "apps.plataforma",
    "apps.contas",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "django.contrib.messages",
    "django.contrib.sessions",
]

# Apps que existem dentro do schema de cada clínica. Cada Fase do plano de
# reescrita acrescenta apps aqui conforme o módulo correspondente é implementado.
TENANT_APPS = [
    "django.contrib.contenttypes",
    "apps.core",
    "apps.tutores",
    "apps.estoque",
    "apps.financeiro",
    "apps.pacientes",
    "apps.atendimentos",
    "apps.agenda",
    "apps.auditoria",
    "apps.usuarios_clinica",
    "apps.dashboard",
]

INSTALLED_APPS = list(SHARED_APPS) + [app for app in TENANT_APPS if app not in SHARED_APPS]

TENANT_MODEL = "plataforma.Clinica"
TENANT_DOMAIN_MODEL = "plataforma.Dominio"
DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)

# URLconf ativado pelo TenantFromSessionMiddleware — não usamos o roteamento
# por subdomínio padrão do django-tenants (ver apps/contas/middleware.py).
URLCONF_PUBLIC = "config.urls_public"
URLCONF_TENANT = "config.urls_tenant"
ROOT_URLCONF = URLCONF_PUBLIC

# -----------------------------------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "apps.contas.middleware.TenantFromSessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.PermissionsPolicyMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.clinica_ativa",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": os.environ.get("DB_NAME", "vettro"),
        "USER": os.environ.get("DB_USER", "vettro"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "vettro"),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "cache_tabela",
    }
}

AUTH_USER_MODEL = "plataforma.Usuario"
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "apps.plataforma.validators.LetrasEDigitosValidator"},
]

LOGIN_URL = "contas:login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "contas:login"

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Sessão de 8h corridas, com renovação a cada request (equivalente ao JWT de
# 8h do sistema FastAPI atual).
SESSION_COOKIE_AGE = 8 * 3600
SESSION_SAVE_EVERY_REQUEST = True

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

# --- Regras de negócio (constantes portadas do sistema FastAPI atual) ------
PLANTAO_ACRESCIMO = 0.5  # +50% sobre serviços/procedimentos (nunca sobre insumos)
CIRURGIA_OUTRA_CIDADE_VALOR = 50  # R$50 fixo
ESTOQUE_BAIXO_LIMIAR = 3  # qtd < 3
VALIDADE_ALERTA_DIAS = 60
LOGIN_MAX_TENTATIVAS = 5
LOGIN_JANELA_SEGUNDOS = 15 * 60

# Provedor de WhatsApp ainda não escolhido pelo usuário (Z-API / Meta Cloud
# API / Twilio, ver §8 do plano) — backend "console" só loga, não envia de
# verdade. Trocar aqui pro backend real assim que decidido, nada mais muda.
WHATSAPP_BACKEND = os.environ.get("WHATSAPP_BACKEND", "apps.agenda.notificacoes.WhatsAppConsoleBackend")

# E-mail — usado pro convite de "definir senha" ao adicionar alguém em
# 🔑 Usuários (§5 do plano). Backend "console" (dev): imprime o e-mail no
# terminal em vez de enviar de verdade. Produção: configurar EMAIL_HOST/
# EMAIL_HOST_USER/EMAIL_HOST_PASSWORD via env var (qualquer SMTP — Gmail,
# SendGrid, Amazon SES, Mailgun... a abstração do Django não amarra a um
# provedor específico, ao contrário do WhatsApp).
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Vettro <nao-responda@vettro.com.br>")
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000")
