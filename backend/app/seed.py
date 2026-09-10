"""Cria o usuário admin inicial se ainda não existir. Uso: python -m app.seed"""

from . import models
from .auth import hash_senha
from .config import settings
from .database import SessionLocal


def run():
    db = SessionLocal()
    try:
        existe = db.query(models.Usuario).filter(models.Usuario.papel == "admin").first()
        if existe:
            print(f"Já existe um admin ({existe.email}). Nada a fazer.")
            return
        admin = models.Usuario(
            nome=settings.admin_nome,
            email=settings.admin_email.strip().lower(),
            senha_hash=hash_senha(settings.admin_senha),
            papel="admin",
        )
        db.add(admin)
        db.commit()
        print(f"Admin criado: {admin.email} (defina ADMIN_SENHA no .env antes de usar em produção).")
    finally:
        db.close()


if __name__ == "__main__":
    run()
