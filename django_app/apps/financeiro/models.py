import uuid

from django.db import models


# Tipos de atendimento com cor própria (mesmas do hub de novo atendimento e da agenda:
# variáveis --et-<tipo> em styles.css).
TIPO_COR_CHOICES = [
    ("consulta", "Consulta"), ("vacinacao", "Vacina"), ("cirurgia", "Procedimento cirúrgico"),
    ("retorno", "Retorno"), ("aplicacao_medicacao", "Aplicação de medicação"), ("curativo", "Curativo"),
    ("emergencia", "Emergência"), ("ambulatorial", "Ambulatorial"), ("exame", "Exame"),
]


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
    # Agenda: tempo que o serviço ocupa na agenda do veterinário (horários livres).
    duracao_min = models.PositiveSmallIntegerField("Duração na agenda (min)", default=30)
    tipo = models.CharField("Tipo de atendimento (cor na agenda)", max_length=20, choices=TIPO_COR_CHOICES, blank=True)
    # Desmarcado = não aparece pra escolher no agendamento (continua cobrável no atendimento).
    # Serviços do tipo "exame" aparecem na seção própria "Exames" do agendamento.
    na_agenda = models.BooleanField("Aparece no agendamento", default=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class TipoExame(models.Model):
    """Tipos de exame que podem ser agendados (ecocardiograma, raio X,
    ultrassonografia...) — seção "Exames" do agendamento. A duração soma na
    duração do agendamento; a clínica (vet/admin) edita em Serviços."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=100, unique=True)
    duracao_min = models.PositiveSmallIntegerField("Duração na agenda (min)", default=60)
    valor = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = "tipos_exames"
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

    # Recebimento da recepção que quitou esta cobrança (junto com outras do mesmo tutor).
    recebimento = models.ForeignKey(
        "financeiro.Recebimento", on_delete=models.SET_NULL, null=True, blank=True, related_name="cobrancas",
    )
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


class Recebimento(models.Model):
    """Pagamento recebido na recepção: quita uma ou mais Cobranças pendentes
    do mesmo tutor de uma vez, dividido em até 4 formas (ex.: 2 cartões, ou
    Pix + dinheiro). A maquininha ainda não é integrada (TEF) — a recepção
    passa o cartão/recebe e confirma aqui. Gera UMA NFS-e com todos os itens."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero = models.PositiveIntegerField(unique=True, editable=False)  # sequencial por clínica
    tutor = models.ForeignKey("tutores.Tutor", on_delete=models.SET_NULL, null=True, blank=True, related_name="recebimentos")
    tutor_nome = models.CharField(max_length=150, blank=True)  # snapshot (LGPD: anonimizado ao excluir o tutor)
    cpf_nota = models.CharField("CPF na nota", max_length=14, blank=True)
    emitir_nota = models.BooleanField(default=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    desconto_tipo = models.CharField(max_length=10, choices=Cobranca.DESCONTO_TIPO_CHOICES, blank=True)
    desconto_informado = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    desconto_valor = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    desconto_motivo = models.CharField(max_length=200, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    troco = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    usuario_nome = models.CharField(max_length=150, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Recebimento {self.numero} · {self.tutor_nome}"

    @property
    def formas_texto(self) -> str:
        return " + ".join(p.descricao for p in self.pagamentos.all())


class PagamentoRecebimento(models.Model):
    FORMA_CHOICES = [
        ("dinheiro", "Dinheiro"), ("pix", "Pix"), ("debito", "Cartão de débito"), ("credito", "Cartão de crédito"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recebimento = models.ForeignKey(Recebimento, on_delete=models.CASCADE, related_name="pagamentos")
    forma = models.CharField(max_length=10, choices=FORMA_CHOICES)
    valor = models.DecimalField(max_digits=10, decimal_places=2)  # valor abatido do total (dinheiro: sem o troco)
    parcelas = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["id"]

    @property
    def descricao(self) -> str:
        parcelas = f" em {self.parcelas}x" if self.forma == "credito" and self.parcelas > 1 else ""
        return f"{self.get_forma_display()}{parcelas} R$ {self.valor}"
