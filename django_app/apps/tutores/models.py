import uuid

from django.db import models

COMO_CONHECEU_CHOICES = [
    ("whatsapp", "WhatsApp"),
    ("indicacao", "Indicação"),
    ("facebook", "Facebook"),
    ("instagram", "Instagram"),
    ("radio", "Rádio"),
    ("tv", "TV"),
    ("google", "Google"),
    ("outro", "Outro"),
]


class Tutor(models.Model):
    """Porte direto de backend/app/models.py:Tutor (ver §3 do plano)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=150)
    tel = models.CharField("Telefone", max_length=20)
    email = models.EmailField(blank=True)
    cpf = models.CharField(max_length=14, blank=True)
    cep = models.CharField(max_length=9, blank=True)
    endereco = models.CharField(max_length=200, blank=True)
    numero = models.CharField(max_length=20, blank=True)
    complemento = models.CharField(max_length=100, blank=True)
    bairro = models.CharField(max_length=100, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    uf = models.CharField(max_length=2, blank=True)
    como_conheceu = models.CharField(max_length=30, choices=COMO_CONHECEU_CHOICES, blank=True)
    obs = models.TextField("Observações", blank=True)

    consentimento_dados = models.BooleanField("Consentimento LGPD", default=False)
    consentimento_em = models.DateTimeField(null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    @property
    def endereco_completo(self) -> str:
        partes = [self.endereco, self.numero, self.complemento, self.bairro, self.cidade, self.uf]
        return ", ".join(p for p in partes if p)
