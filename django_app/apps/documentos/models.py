import uuid

from django.db import models


class ModeloDocumento(models.Model):
    """Modelo de documento da clínica (atestado, termo, autorização...). O
    texto aceita variáveis como {paciente} e {tutor} — ver
    services.VARIAVEIS. Cada clínica começa com os modelos da migração
    0002 e pode editar/criar os seus."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=120, unique=True)
    texto = models.TextField()
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class DocumentoEmitido(models.Model):
    """Documento gerado pra um paciente — o texto final fica congelado aqui
    (editar o modelo depois não muda o que já foi emitido)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paciente = models.ForeignKey("pacientes.Paciente", on_delete=models.CASCADE, related_name="documentos")
    modelo = models.ForeignKey(ModeloDocumento, on_delete=models.SET_NULL, null=True, blank=True, related_name="emitidos")
    titulo = models.CharField(max_length=120)
    texto = models.TextField()
    pac_nome = models.CharField(max_length=150)
    vet_usuario_id = models.UUIDField(null=True, blank=True)
    vet_nome = models.CharField(max_length=150, blank=True)
    vet_crmv = models.CharField(max_length=40, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.titulo} · {self.pac_nome}"
