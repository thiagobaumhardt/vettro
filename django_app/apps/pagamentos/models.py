import uuid

from django.db import models


class TransacaoTEF(models.Model):
    """Uma tentativa de cobrança na maquininha via TEF (§8 do plano). Cada
    linha é um evento imutável — se a clínica tentar cobrar de novo depois
    de uma recusa, isso é uma NOVA TransacaoTEF pra mesma Cobrança, não uma
    edição da anterior (mesmo princípio do ledger de estoque: histórico
    nunca é reescrito).

    `adquirente` é livre (texto, não catálogo fixo) porque o Vettro não deve
    ficar preso a uma maquininha/banco específico — cada clínica configura o
    que já usa (Sicredi, Stone, Cielo...) do lado do provedor TEF (SiTef/
    PayGo), não do lado do Vettro. `terminal_codigo` existe desde já pensando
    em clínica com mais de uma maquininha simultânea: o SiTef exige código de
    terminal distinto por conexão simultânea do mesmo par loja/terminal."""

    STATUS_CHOICES = [
        ("aprovado", "Aprovado"),
        ("negado", "Negado"),
        ("erro", "Erro de comunicação"),
        ("cancelado", "Cancelado"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cobranca = models.ForeignKey(
        "financeiro.Cobranca", on_delete=models.PROTECT, related_name="transacoes_tef",
    )
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    parcelas = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    adquirente = models.CharField("Adquirente/banco", max_length=60, blank=True)
    terminal_codigo = models.CharField("Código de terminal", max_length=30, blank=True)
    bandeira = models.CharField(max_length=30, blank=True)
    nsu = models.CharField(max_length=40, blank=True)
    codigo_autorizacao = models.CharField(max_length=40, blank=True)
    mensagem_erro = models.CharField(max_length=300, blank=True)

    # Sem FK — Usuario vive no schema public (mesmo motivo de AuditLog/MovimentoEstoque).
    usuario_id = models.UUIDField(null=True, blank=True)
    usuario_nome = models.CharField(max_length=150, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Transação TEF"
        verbose_name_plural = "Transações TEF"

    def __str__(self):
        return f"TEF {self.get_status_display()} · R$ {self.valor} · Cobrança {self.cobranca_id}"


class NotaFiscalEmitida(models.Model):
    """Placeholder pra Focus NFe (§8 do plano) — ainda NÃO chama nenhuma API
    (depende de apps.configuracoes/DadosFiscaisClinica, que ainda não existe,
    e de conta Focus NFe homologada). O PDF/XML fica hospedado no próprio
    Focus NFe — não guardamos o arquivo aqui, só as referências."""

    TIPO_CHOICES = [("nfse", "NFS-e (serviço)"), ("nfce", "NFC-e (produto)")]
    STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("emitida", "Emitida"),
        ("erro", "Erro na emissão"),
        ("cancelada", "Cancelada"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Origem: NFS-e sai de uma Cobrança (serviço); NFC-e de uma Venda de balcão.
    cobranca = models.ForeignKey(
        "financeiro.Cobranca", on_delete=models.PROTECT, related_name="notas_fiscais", null=True, blank=True,
    )
    venda = models.ForeignKey(
        "vendas.Venda", on_delete=models.PROTECT, related_name="notas_fiscais", null=True, blank=True,
    )
    tipo = models.CharField(max_length=4, choices=TIPO_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendente")
    # True = emitida pelo emissor de SIMULAÇÃO (sem valor fiscal), enquanto
    # não há conta Focus NFe — ver apps.pagamentos.notas.
    simulacao = models.BooleanField(default=False)
    numero = models.CharField(max_length=20, blank=True)
    chave_acesso = models.CharField(max_length=44, blank=True)
    # Snapshot do que foi enviado ao emissor (prestador, tomador, itens, totais).
    dados = models.JSONField(default=dict, blank=True)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    url_pdf = models.URLField(blank=True)
    url_xml = models.URLField(blank=True)
    mensagem_erro = models.CharField(max_length=500, blank=True)
    emitida_em = models.DateTimeField(null=True, blank=True)
    emitida_por_nome = models.CharField(max_length=150, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Nota fiscal emitida"
        verbose_name_plural = "Notas fiscais emitidas"

    def __str__(self):
        return f"{self.get_tipo_display()} {self.numero or '(sem número)'}"
