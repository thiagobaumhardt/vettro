import uuid

from django.db import models


class Venda(models.Model):
    """Venda de balcão de produtos do estoque, SEM vínculo com paciente
    (ração, antipulgas, acessórios...). Nasce paga — não gera Cobrança — e
    dá baixa no estoque na hora (SD2 `venda_produto`, origem "venda").
    Cancelar estorna o estoque (SD3 `estorno_consumo`)."""

    FORMA_PAGAMENTO_CHOICES = [
        ("dinheiro", "Dinheiro"), ("pix", "Pix"), ("debito", "Cartão de débito"), ("credito", "Cartão de crédito"),
    ]
    DESCONTO_TIPO_CHOICES = [("valor", "R$"), ("percentual", "%")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero = models.PositiveIntegerField(unique=True, editable=False)  # sequencial por clínica
    cliente_nome = models.CharField("Cliente (opcional)", max_length=150, blank=True)

    # [{"insumo_id", "nome", "qtd", "valor"}] — snapshot do preço no momento da venda.
    itens = models.JSONField(default=list)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    desconto_tipo = models.CharField(max_length=10, choices=DESCONTO_TIPO_CHOICES, blank=True)
    desconto_informado = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    desconto_valor = models.DecimalField("Desconto (R$)", max_digits=10, decimal_places=2, default=0)
    desconto_motivo = models.CharField("Motivo do desconto", max_length=200, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    forma_pagamento = models.CharField(max_length=10, choices=FORMA_PAGAMENTO_CHOICES)

    usuario_nome = models.CharField(max_length=150, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    cancelada_em = models.DateTimeField(null=True, blank=True)
    cancelada_por_nome = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Venda #{self.numero}"
