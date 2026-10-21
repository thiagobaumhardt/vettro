import uuid

from django.db import models

from . import cripto


class ConexaoWhatsApp(models.Model):
    """O número de WhatsApp de UMA clínica na Cloud API da Meta (schema
    public — o webhook da Meta chega sem sessão e precisa achar a clínica
    pelo phone_number_id antes de abrir o schema dela).

    Cada clínica tem a PRÓPRIA conta WhatsApp Business (WABA): a Meta cobra
    as mensagens direto da clínica e os templates ficam dentro da WABA dela.
    Fase 1 (hoje, só a Lume): conexão manual pela plataforma, com o app Meta
    no portfólio da Lume. Fase 2: o Vettro vira Tech Provider (um app Meta
    só, da plataforma) e cada clínica conecta sozinha pelo Embedded Signup.
    Ver docs/whatsapp-meta.md."""

    class Status(models.TextChoices):
        ATIVA = "ativa", "Conectado"
        ERRO = "erro", "Com erro"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinica = models.OneToOneField("plataforma.Clinica", on_delete=models.CASCADE, related_name="whatsapp")
    waba_id = models.CharField("ID da conta WhatsApp Business (WABA)", max_length=64)
    phone_number_id = models.CharField("ID do número", max_length=64, unique=True)
    numero_exibicao = models.CharField("Número", max_length=30, blank=True)
    nome_exibicao = models.CharField("Nome exibido", max_length=200, blank=True)
    qualidade = models.CharField("Qualidade do número", max_length=20, blank=True)
    # Número que continua no app WhatsApp Business do celular (coexistência):
    # as respostas dos tutores aparecem no celular da clínica normalmente.
    coexistencia = models.BooleanField(default=False)
    token_cifrado = models.TextField(blank=True)
    pin_cifrado = models.TextField(blank=True)  # PIN de 2 etapas usado no registro do número
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ATIVA)
    erro = models.TextField(blank=True)
    # {nome_do_modelo: {"status": "APPROVED"|"PENDING"|"REJECTED"|..., "categoria": ..., "motivo": ...}}
    modelos = models.JSONField(default=dict, blank=True)
    conectado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Conexão de WhatsApp"
        verbose_name_plural = "Conexões de WhatsApp"

    def __str__(self):
        return f"{self.clinica} — {self.numero_exibicao or self.phone_number_id}"

    @property
    def token(self) -> str:
        return cripto.decifrar(self.token_cifrado)

    @token.setter
    def token(self, valor: str):
        self.token_cifrado = cripto.cifrar(valor)

    @property
    def pin(self) -> str:
        return cripto.decifrar(self.pin_cifrado)

    @pin.setter
    def pin(self, valor: str):
        self.pin_cifrado = cripto.cifrar(valor)

    @property
    def ativa(self) -> bool:
        return self.status == self.Status.ATIVA and bool(self.token)

    def modelo_aprovado(self, nome: str) -> bool:
        return (self.modelos.get(nome) or {}).get("status") == "APPROVED"
