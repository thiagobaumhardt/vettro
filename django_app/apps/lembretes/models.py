import uuid

from django.core.validators import FileExtensionValidator
from django.db import models

from apps.core.storage import TenantFileSystemStorage
from apps.core.validators import TamanhoArquivoValidator


class Lembrete(models.Model):
    """Mensagem de WhatsApp com texto livre enviada manualmente pra tutores
    escolhidos pelo usuário (diferente do lembrete automático de agendamento,
    apps.agenda.management.commands.enviar_lembretes_whatsapp)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    texto = models.TextField()
    # Imagem opcional no topo da mensagem (template vettro_aviso_imagem).
    imagem = models.ImageField(
        upload_to="lembretes/", storage=TenantFileSystemStorage(), null=True, blank=True,
        validators=[TamanhoArquivoValidator(5 * 1024 * 1024, "Imagem"), FileExtensionValidator(["jpg", "jpeg", "png"])],
    )
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
    mensagem = models.ForeignKey("MensagemWhatsApp", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["tutor_nome"]


class MensagemWhatsApp(models.Model):
    """Toda mensagem de WhatsApp da clínica — enviada (lembretes automáticos,
    avisos do menu Lembretes, teste) ou recebida (resposta do tutor). O status
    de entrega/leitura chega depois, pelo webhook da Meta
    (apps.whatsapp.webhook), casado pelo `wamid`."""

    class Tipo(models.TextChoices):
        AGENDAMENTO = "agendamento", "Lembrete de agendamento"
        VACINA = "vacina", "Lembrete de vacina"
        RETORNO = "retorno", "Lembrete de retorno"
        AVISO = "aviso", "Aviso"
        TESTE = "teste", "Teste"
        RESPOSTA = "resposta", "Resposta do tutor"

    class Status(models.TextChoices):
        ENVIADA = "enviada", "Enviada"
        ENTREGUE = "entregue", "Entregue"
        LIDA = "lida", "Lida"
        FALHOU = "falhou", "Falhou"
        RECEBIDA = "recebida", "Recebida"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    tutor = models.ForeignKey("tutores.Tutor", on_delete=models.SET_NULL, null=True, blank=True, related_name="mensagens_whatsapp")
    # Snapshots — limpos por apps.tutores.services.escrubar_snapshots_tutor quando o tutor é excluído.
    telefone = models.CharField(max_length=20, blank=True)
    texto = models.TextField(blank=True)
    modelo = models.CharField(max_length=60, blank=True)
    wamid = models.CharField(max_length=128, blank=True, db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices)
    erro = models.TextField(blank=True)
    # Resposta "SAIR": o consentimento de WhatsApp do tutor foi revogado (LGPD).
    descadastrou = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em"]

    @property
    def enviada(self) -> bool:
        return self.status in (self.Status.ENVIADA, self.Status.ENTREGUE, self.Status.LIDA)
