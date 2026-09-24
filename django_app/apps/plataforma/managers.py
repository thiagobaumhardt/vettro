from django.contrib.auth.base_user import BaseUserManager


class UsuarioManager(BaseUserManager):
    """Identidade global (schema public) — uma pessoa, um e-mail, N clínicas via UsuarioClinica."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("O e-mail é obrigatório.")
        email = self.normalize_email(email).lower()
        usuario = self.model(email=email, **extra_fields)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_platform_admin", False)
        extra_fields.setdefault("is_active", True)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("nome", email)
        extra_fields["is_platform_admin"] = True
        extra_fields["is_active"] = True
        extra_fields["is_superuser"] = True
        return self._create_user(email, password, **extra_fields)
