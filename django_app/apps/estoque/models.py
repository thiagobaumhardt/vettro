import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


# Tabela de origem da mercadoria da NF-e (campo "orig" do ICMS).
ORIGEM_CHOICES = [
    ("0", "0 — Nacional"),
    ("1", "1 — Estrangeira, importação direta"),
    ("2", "2 — Estrangeira, adquirida no mercado interno"),
    ("3", "3 — Nacional, conteúdo de importação acima de 40%"),
    ("4", "4 — Nacional, produção conforme processos básicos"),
    ("5", "5 — Nacional, conteúdo de importação até 40%"),
    ("6", "6 — Estrangeira, importação direta, sem similar nacional"),
    ("7", "7 — Estrangeira, mercado interno, sem similar nacional"),
    ("8", "8 — Nacional, conteúdo de importação acima de 70%"),
]


class Insumo(models.Model):
    """Porte de backend/app/models.py:Insumo (§3 do plano) + campos fiscais
    (ncm/cfop/cst_csosn, tipo_fiscal) pra emissão de NFC-e na Fase 6.

    `qtd` é um CACHE mantido pelo ledger (MovimentoEstoque) — nunca mutado
    diretamente fora de apps.estoque.services.registrar_movimento.

    Unidades (padrão de mercado — 1ª/2ª unidade + fator, como o Protheus):
    o estoque, o preço (`valor`) e o consumo são sempre na UNIDADE DE USO
    (`unidade`: seringa, ml, comprimido). A compra é na EMBALAGEM
    (`embalagem`, ex. "caixa"), que contém `unidades_por_pacote` unidades de
    uso (ex. 1 caixa = 100 seringas; 1 frasco = 50 ml)."""

    TIPO_FISCAL_CHOICES = [("produto", "Produto"), ("servico", "Serviço")]
    UNIDADE_CHOICES = [
        ("un", "unidade"), ("ml", "ml"), ("g", "g"), ("comp", "comprimido"), ("caps", "cápsula"),
        ("dose", "dose"), ("amp", "ampola"), ("par", "par"), ("kg", "kg"), ("L", "litro"), ("cm", "cm"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=150)
    categoria = models.CharField(max_length=100, blank=True)
    valor = models.DecimalField("Preço por unidade de uso", max_digits=10, decimal_places=2)
    qtd = models.DecimalField("Quantidade em estoque", max_digits=12, decimal_places=3, default=0)
    unidade = models.CharField("Unidade de uso", max_length=5, choices=UNIDADE_CHOICES, default="un")
    embalagem = models.CharField(
        "Embalagem de compra", max_length=30, blank=True, help_text='Ex.: "caixa", "frasco", "pacote".',
    )
    unidades_por_pacote = models.DecimalField(
        "Conteúdo da embalagem", max_digits=10, decimal_places=3, default=1,
        validators=[MinValueValidator(Decimal("0.001"))],
        help_text="Quantas unidades de uso vêm em uma embalagem (ex.: 100 seringas, 50 ml).",
    )
    estoque_minimo = models.DecimalField(
        "Estoque mínimo", max_digits=12, decimal_places=3, null=True, blank=True,
        help_text="Na unidade de uso. Em branco = regra geral (menos de 3).",
    )
    codigo_barras = models.CharField(max_length=64, unique=True, null=True, blank=True)
    data_validade = models.DateField(null=True, blank=True)
    lote = models.CharField(max_length=60, blank=True)
    ncm = models.CharField(
        "NCM", max_length=8, blank=True,
        help_text="Preenchido automaticamente ao importar XML de NF-e do fornecedor.",
    )
    # Tributação na REVENDA (venda de balcão, NFC-e). Normalmente nada disso é
    # digitado: NCM, origem e ST vêm do XML do fornecedor, e CFOP/CSOSN saem da
    # regra fiscal da clínica (core.ConfiguracaoClinica) — ver apps.estoque.fiscal.
    tem_st = models.BooleanField(
        "Substituição tributária (ICMS-ST)", default=False,
        help_text="Marcado sozinho ao importar o XML do fornecedor quando o ICMS já veio recolhido.",
    )
    origem = models.CharField("Origem da mercadoria", max_length=1, choices=ORIGEM_CHOICES, default="0")
    cfop = models.CharField(
        "CFOP (exceção)", max_length=4, blank=True,
        help_text="Deixe em branco para usar a regra fiscal da clínica.",
    )
    cst_csosn = models.CharField(
        "CST/CSOSN (exceção)", max_length=4, blank=True,
        help_text="Deixe em branco para usar a regra fiscal da clínica.",
    )
    tipo_fiscal = models.CharField(max_length=10, choices=TIPO_FISCAL_CHOICES, default="produto")
    obs = models.TextField("Observações", blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    @property
    def limite_baixo(self) -> Decimal:
        """Estoque mínimo do produto ou, sem ele, a regra geral (< 3)."""
        from django.conf import settings

        return self.estoque_minimo if self.estoque_minimo is not None else Decimal(settings.ESTOQUE_BAIXO_LIMIAR)

    @property
    def status_estoque(self) -> str:
        if self.qtd <= 0:
            return "zerado"
        if self.qtd < self.limite_baixo:
            return "baixo"
        return "ok"

    # Rótulo curto ao lado de quantidades ("200 un.", "47,5 ml", "3 comp.").
    UNIDADE_ABREVIADA = {"un": "un.", "comp": "comp.", "caps": "cáps.", "amp": "amp.", "L": "L"}

    @property
    def unidade_rotulo(self) -> str:
        return self.UNIDADE_ABREVIADA.get(self.unidade, self.unidade)

    @property
    def fracionado(self) -> bool:
        """Compra em embalagem com mais de uma unidade de uso (caixa de 100, frasco de 50 ml)."""
        return self.unidades_por_pacote != 1


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
        ("estorno_consumo", "Estorno de consumo"),
    ]
    # Subtipos SD3 que DEVOLVEM ao estoque — os demais SD3 retiram.
    SUBTIPOS_SD3_POSITIVOS = {"ajuste_positivo", "estorno_consumo"}

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name="movimentos")
    tipo = models.CharField(max_length=3, choices=TIPO_CHOICES)
    subtipo = models.CharField(max_length=30, choices=SUBTIPO_CHOICES)
    # Sempre na unidade de uso do insumo (ex.: 2.5 ml), já convertida.
    quantidade = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    valor_unitario = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True, help_text="Por unidade de uso.",
    )

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
