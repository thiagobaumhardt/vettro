import uuid

from django.db import models


class Lembrete(models.Model):
    """Mensagem de WhatsApp com texto livre enviada manualmente pra tutores
    escolhidos pelo usuário (diferente do lembrete automático de agendamento,
    apps.agenda.management.commands.enviar_lembretes_whatsapp)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    texto = models.TextField()
    # Sem FK — Usuario vive no schema public (mesmo motivo do AuditLog).
    usuario_id = models.UUIDField(null=True, blank=True)
    usuario_nome = models.CharField(max_length=150, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Lembrete {self.criado_em:%d/%m/%Y %H:%M}"


class EnvioLembrete(models.Model):
    """Um destinatário de um Lembrete — resultado do envio pra cada tutor."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lembrete = models.ForeignKey(Lembrete, on_delete=models.CASCADE, related_name="envios")
    tutor = models.ForeignKey("tutores.Tutor", on_delete=models.SET_NULL, null=True, blank=True, related_name="lembretes")
    # Snapshots — limpos por apps.tutores.services.escrubar_snapshots_tutor quando o tutor é excluído.
    tutor_nome = models.CharField(max_length=150, blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    enviado = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["tutor_nome"]
