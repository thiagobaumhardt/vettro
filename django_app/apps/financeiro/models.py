import uuid

from django.db import models


class Servico(models.Model):
    """Porte de backend/app/models.py:Servico. `codigo_servico_municipal`
    fica pronto pra Fase 6 (NFS-e — cada prefeitura numera diferente, ver
    atualização do plano sobre dados fiscais)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=150)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    # Serviço cobrado por tempo/quantidade (oxigenoterapia por hora, internação
    # por diária): o valor é por essa unidade e o atendimento informa quantas.
    # Em branco = cobrado por vez.
    unidade_cobranca = models.CharField(
        "Cobrado por", max_length=20, blank=True, help_text='Ex.: "hora", "diária", "sessão". Em branco = por vez.',
    )
    descricao = models.TextField(blank=True)
    codigo_servico_municipal = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class CirurgiaCategoria(models.Model):
    """Catálogo de procedimentos cirúrgicos — preço por faixa de peso do
    paciente (P/M/G), porte de backend/app/models.py:CirurgiaCategoria."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=150)
    valor_p = models.DecimalField("Até 10kg", max_digits=10, decimal_places=2, null=True, blank=True)
    valor_m = models.DecimalField("10–25kg", max_digits=10, decimal_places=2, null=True, blank=True)
    valor_g = models.DecimalField("Acima de 25kg", max_digits=10, decimal_places=2, null=True, blank=True)
    descricao = models.TextField(blank=True)

    class Meta:
        ordering = ["nome"]
        verbose_name_plural = "Categorias de cirurgia"

    def __str__(self):
        return self.nome


class Cobranca(models.Model):
    """Porte de backend/app/models.py:Cobranca. Gerada automaticamente por
    Anamnese/Cirurgia/Atendimento com itens faturáveis, ou manualmente (Fase 4)."""

    STATUS_CHOICES = [("pendente", "Pendente"), ("pago", "Pago")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paciente = models.ForeignKey("pacientes.Paciente", on_delete=models.CASCADE, related_name="cobrancas")
    servicos = models.JSONField(default=list, blank=True)
    insumos = models.JSONField(default=list, blank=True)
    obs = models.TextField(blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendente")
    tutor_nome = models.CharField(max_length=150, blank=True)

    # Preenchidos ao marcar como pago. `total` continua sendo o valor cheio;
    # o que o tutor pagou de fato é `valor_pago` = total − desconto_valor.
    DESCONTO_TIPO_CHOICES = [("valor", "R$"), ("percentual", "%")]
    desconto_tipo = models.CharField(max_length=10, choices=DESCONTO_TIPO_CHOICES, blank=True)
    desconto_informado = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="O que foi digitado: reais ou percentual, conforme desconto_tipo.",
    )
    desconto_valor = models.DecimalField("Desconto (R$)", max_digits=10, decimal_places=2, default=0)
    desconto_motivo = models.CharField("Motivo do desconto", max_length=200, blank=True)
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    pago_em = models.DateTimeField(null=True, blank=True)
    pago_por_nome = models.CharField(max_length=150, blank=True)

    # Atendimento que gerou esta cobrança (se veio de um) — permite remover
    # a cobrança pendente quando o atendimento é excluído.
    atendimento = models.ForeignKey(
        "atendimentos.Atendimento", on_delete=models.SET_NULL, null=True, blank=True, related_name="cobrancas"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Cobrança {self.pk} · {self.paciente.nome} · R$ {self.total}"
