import uuid

from django.db import models


class AuditLog(models.Model):
    """Trilha de auditoria por clínica — porte de backend/app/models.py:AuditLog.
    `usuario_id` é um UUIDField SEM FK: Usuario vive no schema public,
    schemas de tenant não podem ter FK cruzando schema (§3 do plano) —
    `usuario_nome` denormalizado é a única referência confiável."""

    ACAO_CHOICES = [
        ("login_ok", "Login"), ("criar", "Criou"), ("atualizar", "Atualizou"),
        ("excluir", "Excluiu"), ("exportar", "Exportou"),
    ]
    ENTIDADE_CHOICES = [
        ("tutor", "Tutor"), ("paciente", "Paciente"), ("insumo", "Insumo"), ("auth", "Autenticação"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario_id = models.UUIDField(null=True, blank=True)
    usuario_nome = models.CharField(max_length=150, blank=True)
    acao = models.CharField(max_length=30, choices=ACAO_CHOICES)
    entidade = models.CharField(max_length=30, choices=ENTIDADE_CHOICES)
    entidade_id = models.UUIDField(null=True, blank=True)
    detalhe = models.CharField(max_length=300, blank=True)
    ip = models.CharField(max_length=45, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.usuario_nome} {self.acao} {self.entidade}"
