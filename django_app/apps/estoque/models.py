import uuid

from django.db import models


class Insumo(models.Model):
    """Porte de backend/app/models.py:Insumo (§3 do plano) + campos fiscais
    (ncm/cfop/cst_csosn, tipo_fiscal) pra emissão de NFC-e na Fase 6.

    `qtd` é um CACHE mantido pelo ledger (MovimentoEstoque) — nunca mutado
    diretamente fora de apps.estoque.services.registrar_movimento."""

    TIPO_FISCAL_CHOICES = [("produto", "Produto"), ("servico", "Serviço")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=150)
    categoria = models.CharField(max_length=100, blank=True)
    valor = models.DecimalField("Valor unitário", max_digits=10, decimal_places=2)
    qtd = models.IntegerField("Quantidade em estoque", default=0)
    codigo_barras = models.CharField(max_length=64, unique=True, null=True, blank=True)
    unidades_por_pacote = models.PositiveIntegerField(default=1)
    data_validade = models.DateField(null=True, blank=True)
    lote = models.CharField(max_length=60, blank=True)
    ncm = models.CharField(
        "NCM", max_length=8, blank=True,
        help_text="Preenchido automaticamente ao importar XML de NF-e do fornecedor.",
    )
    cfop = models.CharField("CFOP", max_length=4, blank=True)
    cst_csosn = models.CharField("CST/CSOSN", max_length=4, blank=True)
    tipo_fiscal = models.CharField(max_length=10, choices=TIPO_FISCAL_CHOICES, default="produto")
    obs = models.TextField("Observações", blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    @property
    def status_estoque(self) -> str:
        if self.qtd <= 0:
            return "zerado"
        from django.conf import settings

        if self.qtd < settings.ESTOQUE_BAIXO_LIMIAR:
            return "baixo"
        return "ok"


class MovimentoEstoque(models.Model):
    """Ledger de movimentações de estoque, estilo Protheus SD1/SD2/SD3 (§3 do
    plano) — substitui o incremento/decremento direto de Insumo.qtd."""

    SD1_ENTRADA = "SD1"
    SD2_SAIDA = "SD2"
    SD3_INTERNO = "SD3"
    TIPO_CHOICES = [
        (SD1_ENTRADA, "Entrada (SD1)"),
        (SD2_SAIDA, "Saída (SD2)"),
        (SD3_INTERNO, "Interno (SD3)"),
    ]

    SUBTIPO_CHOICES = [
        ("nfe_fornecedor", "NF-e do fornecedor"),
        ("manual_sem_nota", "Manual sem nota fiscal"),
        ("venda_servico", "Venda/consumo em serviço"),
        ("venda_produto", "Venda de produto"),
        ("consumo_atendimento", "Consumo em atendimento"),
        ("ajuste_positivo", "Ajuste positivo"),
        ("ajuste_negativo", "Ajuste negativo"),
        ("perda", "Perda"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name="movimentos")
    tipo = models.CharField(max_length=3, choices=TIPO_CHOICES)
    subtipo = models.CharField(max_length=30, choices=SUBTIPO_CHOICES)
    quantidade = models.PositiveIntegerField()
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Referência genérica ao documento de origem (Cobranca/Anamnese/Cirurgia/
    # Atendimento/lote de importação) — sem FK real, são modelos de apps
    # diferentes e o alvo varia por origem_tipo.
    origem_tipo = models.CharField(max_length=30, blank=True)
    origem_id = models.UUIDField(null=True, blank=True)

    nota_fiscal_chave = models.CharField(max_length=44, blank=True)
    nota_fiscal_numero = models.CharField(max_length=20, blank=True)
    observacao = models.CharField(max_length=300, blank=True)

    # Sem FK — Usuario vive no schema public, tenant não pode ter FK cruzando
    # schema (mesmo motivo do AuditLog, ver §3 do plano).
    usuario_id = models.UUIDField(null=True, blank=True)
    usuario_nome = models.CharField(max_length=150, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.insumo.nome} · {self.quantidade}"
