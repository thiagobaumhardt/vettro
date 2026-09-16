from pydantic import field_validator
from pydantic_settings import BaseSettings

DEFAULT_JWT_SECRET = "troque-esta-chave-em-producao"
DEFAULT_ADMIN_SENHA = "vettro123"


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://vettro:vettro@db:5432/vettro"
    cors_origins: str = "*"
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_expira_horas: int = 8
    admin_nome: str = "Administrador"
    admin_email: str = "admin@vettro.local"
    admin_senha: str = DEFAULT_ADMIN_SENHA

    class Config:
        env_file = ".env"

    @field_validator("database_url")
    @classmethod
    def _normaliza_driver_postgres(cls, v: str) -> str:
        # Plataformas como Railway/Render fornecem DATABASE_URL como "postgres://" ou
        # "postgresql://" (sem driver). Precisamos do driver psycopg (v3) explícito.
        if v.startswith("postgres://"):
            return "postgresql+psycopg://" + v[len("postgres://") :]
        if v.startswith("postgresql://"):
            return "postgresql+psycopg://" + v[len("postgresql://") :]
        return v


settings = Settings()
