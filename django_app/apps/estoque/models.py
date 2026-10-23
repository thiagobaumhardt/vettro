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



# Unidade comercial na nota de venda (uCom da NFC-e) a partir da unidade de uso,
# quando o produto não informa uma própria (`unidade_venda`).
UNIDADE_NOTA_PADRAO = {
    "un": "UN", "ml": "ML", "g": "G", "comp": "COMP", "caps": "CAPS", "dose": "DOSE",
    "amp": "AMP", "par": "PAR", "kg": "KG", "L": "L", "cm": "CM",
}


def proximo_codigo(modelo, prefixo: str = "", digitos: int = 3) -> str:
    """Próximo código interno sequencial (001, 002... / SERV001...) — o número
    legível que aparece na tela e vai no cProd da nota (pedido do contador).
    Códigos editados à mão fora do padrão são ignorados na contagem."""
    maior = 0
    for codigo in modelo.objects.exclude(codigo__isnull=True).values_list("codigo", flat=True):
        resto = codigo[len(prefixo):] if codigo.startswith(prefixo) else ""
        if resto.isdigit():
            maior = max(maior, int(resto))
    return f"{prefixo}{maior + 1:0{digitos}d}"


class InsumoQuerySet(models.QuerySet):
    def para_atendimento(self):
        """Usáveis nos atendimentos (uso interno) — exclui os só de revenda."""
        return self.exclude(finalidade="revenda")

    def para_venda(self):
        """Vendáveis no balcão — exclui os só de uso interno."""
        return self.exclude(finalidade="uso_interno")


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

    # Contador: separar o medicamento vendido ao cliente do consumido no
    # atendimento. "ambos" = aparece nos dois lugares (padrão).
    FINALIDADE_CHOICES = [
        ("ambos", "Uso interno e revenda"),
        ("uso_interno", "Só uso interno (atendimentos)"),
        ("revenda", "Só revenda (balcão)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Código interno legível (001, 002...), gerado sozinho — vai no cProd da NFC-e.
    codigo = models.CharField("Código", max_length=20, unique=True, null=True, blank=True)
    nome = models.CharField(max_length=150)
    categoria = models.CharField(max_length=100, blank=True)
    finalidade = models.CharField("Finalidade", max_length=12, choices=FINALIDADE_CHOICES, default="ambos")
    valor = models.DecimalField("Preço por unidade de uso", max_digits=10, decimal_places=2)
    qtd = models.DecimalField("Quantidade em estoque", max_digits=12, decimal_places=3, default=0)
    unidade = models.CharField("Unidade de uso", max_length=5, choices=UNIDADE_CHOICES, default="un")
    unidade_venda = models.CharField(
        "Unidade na nota de venda", max_length=6, blank=True,
        help_text="Sigla da nota (UN, CX, FR...). Em branco = a da unidade de uso.",
    )
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
    # CEST: obrigatório na nota de produto com ICMS-ST (Convênio ICMS 142/2018).
    cest = models.CharField(
        "CEST", max_length=7, blank=True,
        help_text="Preenchido automaticamente ao importar XML de NF-e do fornecedor.",
    )
    # PIS/COFINS monofásico (ex.: medicamentos): o imposto já foi pago pelo
    # fabricante, a revenda sai com alíquota zero (CST 04) e, no Simples, essa
    # receita é separada no PGDAS — a clínica não paga PIS/COFINS de novo.
    pis_cofins_monofasico = models.BooleanField(
        "PIS/COFINS monofásico", default=False,
        help_text="Marcado sozinho ao importar o XML do fornecedor (CST de PIS 02, 03 ou 04).",
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
    # Último custo de entrada (por unidade de uso): lucro, análise de estoque e capital parado.
    custo = models.DecimalField(
        "Último custo (por unidade de uso)", max_digits=12, decimal_places=4, null=True, blank=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    objects = InsumoQuerySet.as_manager()

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = proximo_codigo(Insumo)
        super().save(*args, **kwargs)

    @property
    def unidade_nota(self) -> str:
        return (self.unidade_venda or UNIDADE_NOTA_PADRAO.get(self.unidade, "UN")).upper()

    @property
    def lucro_unitario(self) -> Decimal | None:
        """Venda − compra, por unidade de uso (None sem valor de compra)."""
        return (self.valor - self.custo).quantize(Decimal("0.01")) if self.custo is not None else None

    @property
    def margem(self) -> Decimal | None:
        """Lucro sobre o valor de venda, em %."""
        if self.custo is None or not self.valor:
            return None
        return ((self.valor - self.custo) / self.valor * 100).quantize(Decimal("0.1"))

    @property
    def custo_referencia(self) -> Decimal:
        """Último custo de compra; sem ele, o preço (estimativa)."""
        return self.custo if self.custo is not None else self.valor

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
        # Outras saídas (estilo SimplesVet) — ver SaidaEstoque.
        ("consumo_interno", "Consumo interno"),
        ("perda_validade", "Perda de validade"),
        ("avaria", "Avaria"),
        ("doacao", "Doação"),
        ("devolucao_compra", "Devolução de compra"),
        ("inventario_positivo", "Inventário (sobra)"),
        ("inventario_negativo", "Inventário (falta)"),
        ("devolucao_venda", "Devolução de venda"),
    ]
    # Subtipos SD3 que DEVOLVEM ao estoque — os demais SD3 retiram.
    SUBTIPOS_SD3_POSITIVOS = {"ajuste_positivo", "estorno_consumo", "inventario_positivo", "devolucao_venda"}

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
    # Entrada SD1 que NÃO foi compra paga (estoque inicial, doação, brinde):
    # não aparece como saída de dinheiro em Financeiro (apps.financeiro.caixa).
    fora_do_financeiro = models.BooleanField(default=False)

    # Sem FK — Usuario vive no schema public, tenant não pode ter FK cruzando
    # schema (mesmo motivo do AuditLog, ver §3 do plano).
    usuario_id = models.UUIDField(null=True, blank=True)
    usuario_nome = models.CharField(max_length=150, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.insumo.nome} · {self.quantidade}"



class MotivoSaida(models.Model):
    """Motivos livres e ilimitados das outras saídas ("Uso no banho", "Uso na internação")."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class SaidaEstoque(models.Model):
    """Outras saídas de estoque (consumo interno, perda de validade, avaria,
    doação, devolução de compra) — cada item vira um MovimentoEstoque SD3
    do subtipo correspondente, na hora."""

    TIPO_CHOICES = [
        ("consumo_interno", "Consumo interno"), ("perda_validade", "Perda de validade"),
        ("avaria", "Avaria"), ("doacao", "Doação"), ("devolucao_compra", "Devolução de compra"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    motivo = models.ForeignKey(MotivoSaida, on_delete=models.SET_NULL, null=True, blank=True, related_name="saidas")
    beneficiario = models.CharField("Beneficiário (doação)", max_length=150, blank=True)
    detalhe = models.CharField("Detalhes", max_length=300, blank=True, help_text="Ex.: o que aconteceu na avaria.")
    solicitante = models.CharField(max_length=150, blank=True)
    data = models.DateField()
    total_custo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    usuario_nome = models.CharField(max_length=150, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data", "-criado_em"]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.data}"


class ItemSaidaEstoque(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    saida = models.ForeignKey(SaidaEstoque, on_delete=models.CASCADE, related_name="itens")
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name="saidas")
    quantidade = models.DecimalField(max_digits=12, decimal_places=3)
    custo_unitario = models.DecimalField(max_digits=12, decimal_places=4, default=0)

    @property
    def custo_total(self) -> Decimal:
        return (self.quantidade * self.custo_unitario).quantize(Decimal("0.01"))


class Inventario(models.Model):
    """Contagem física (pelo celular, lendo código de barras). Ao finalizar, as
    diferenças viram ajustes SD3 inventario_positivo/negativo e a validade
    contada atualiza o produto."""

    STATUS_CHOICES = [("aberto", "Em contagem"), ("finalizado", "Finalizado"), ("cancelado", "Cancelado")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    descricao = models.CharField(max_length=150, help_text='Ex.: "Prateleira de vacinas", "Geral outubro".')
    categoria = models.CharField(max_length=100, blank=True, help_text="Em branco = todos os produtos.")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="aberto")
    criado_por_nome = models.CharField(max_length=150, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    finalizado_em = models.DateTimeField(null=True, blank=True)
    finalizado_por_nome = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return self.descricao


class ItemInventario(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventario = models.ForeignKey(Inventario, on_delete=models.CASCADE, related_name="itens")
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name="contagens")
    qtd_contada = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    validade_contada = models.DateField(null=True, blank=True)
    qtd_sistema = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True,
                                      help_text="Estoque do sistema no momento em que o inventário foi finalizado.")
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["insumo__nome"]
        unique_together = [("inventario", "insumo")]
