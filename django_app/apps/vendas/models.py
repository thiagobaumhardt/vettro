import uuid

from django.db import models


class Venda(models.Model):
    """Venda de balcão de produtos do estoque, SEM vínculo com paciente
    (ração, antipulgas, acessórios...). Cliente é opcional: se ele der o CPF,
    a venda guarda o CPF e, se já for tutor cadastrado, liga ao Tutor. Não gera Cobrança e
    dá baixa no estoque na hora (SD2 `venda_produto`, origem "venda").
    Dinheiro nasce paga; cartão/Pix nasce "aguardando" e só fica paga quando a
    maquininha aprova (TransacaoTEF) — a NFC-e sai depois disso, com os dados
    do pagamento (exigência do RS). Cancelar estorna o estoque (SD3
    `estorno_consumo`) e o pagamento na maquininha."""

    FORMA_PAGAMENTO_CHOICES = [
        ("dinheiro", "Dinheiro"), ("pix", "Pix"), ("debito", "Cartão de débito"), ("credito", "Cartão de crédito"),
    ]
    FORMAS_MAQUININHA = ("debito", "credito", "pix")
    DESCONTO_TIPO_CHOICES = [("valor", "R$"), ("percentual", "%")]
    PAGAMENTO_STATUS_CHOICES = [("aguardando", "Aguardando maquininha"), ("pago", "Pago")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero = models.PositiveIntegerField(unique=True, editable=False)  # sequencial por clínica
    cliente_nome = models.CharField("Cliente (opcional)", max_length=150, blank=True)
    # CPF na nota (opcional, perguntado no balcão). Se for de um tutor cadastrado, liga a venda a ele.
    cliente_cpf = models.CharField("CPF do cliente", max_length=14, blank=True)
    tutor = models.ForeignKey(
        "tutores.Tutor", on_delete=models.SET_NULL, null=True, blank=True, related_name="vendas",
    )

    # [{"insumo_id", "nome", "qtd", "valor"}] — snapshot do preço no momento da venda.
    itens = models.JSONField(default=list)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    desconto_tipo = models.CharField(max_length=10, choices=DESCONTO_TIPO_CHOICES, blank=True)
    desconto_informado = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    desconto_valor = models.DecimalField("Desconto (R$)", max_digits=10, decimal_places=2, default=0)
    desconto_motivo = models.CharField("Motivo do desconto", max_length=200, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    forma_pagamento = models.CharField(max_length=10, choices=FORMA_PAGAMENTO_CHOICES)
    parcelas = models.PositiveSmallIntegerField(default=1)
    pagamento_status = models.CharField(max_length=12, choices=PAGAMENTO_STATUS_CHOICES, default="pago")

    usuario_nome = models.CharField(max_length=150, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    cancelada_em = models.DateTimeField(null=True, blank=True)
    cancelada_por_nome = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Venda #{self.numero}"

    @property
    def aguardando_pagamento(self) -> bool:
        return self.pagamento_status == "aguardando" and not self.cancelada_em

    @property
    def transacao_aprovada(self):
        return self.transacoes_tef.filter(status__in=("aprovado", "estornado")).first()

    @property
    def custo_total(self):
        """Soma do valor de compra dos itens (guardado na hora da venda).
        None se algum item não tinha valor de compra cadastrado."""
        from decimal import Decimal

        total = Decimal("0")
        for item in self.itens:
            if item.get("custo") is None:
                return None
            total += Decimal(item["custo"]) * Decimal(str(item["qtd"]))
        return total.quantize(Decimal("0.01"))

    @property
    def lucro(self):
        """Total recebido (já com desconto) − valor de compra dos itens."""
        custo = self.custo_total
        return None if custo is None else self.total - custo
