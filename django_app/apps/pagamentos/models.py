import uuid

from django.db import models


class TransacaoTEF(models.Model):
    """Uma tentativa de cobrança na maquininha via TEF (§8 do plano), de uma
    Venda de balcão (cartão/Pix — exigência da NFC-e no RS) ou de uma
    Cobrança. Cada tentativa é uma linha: se a clínica cobrar de novo depois
    de uma recusa, isso é uma NOVA TransacaoTEF, não uma edição da anterior.
    O status de uma linha só anda pra frente: pendente → aprovado/negado/
    erro/cancelado, e aprovado → estornado (venda cancelada).

    `adquirente` é livre (texto, não catálogo fixo) porque o Vettro não deve
    ficar preso a uma maquininha/banco específico — cada clínica configura o
    que já usa (Sicredi, Stone, Cielo...) do lado do provedor TEF (SiTef/
    PayGo), não do lado do Vettro. `terminal_codigo` existe desde já pensando
    em clínica com mais de uma maquininha simultânea: o SiTef exige código de
    terminal distinto por conexão simultânea do mesmo par loja/terminal."""

    STATUS_CHOICES = [
        ("pendente", "Aguardando maquininha"),
        ("aprovado", "Aprovado"),
        ("negado", "Negado"),
        ("erro", "Erro de comunicação"),
        ("cancelado", "Cancelado"),
        ("estornado", "Estornado"),
    ]
    FORMA_CHOICES = [("debito", "Cartão de débito"), ("credito", "Cartão de crédito"), ("pix", "Pix")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cobranca = models.ForeignKey(
        "financeiro.Cobranca", on_delete=models.PROTECT, related_name="transacoes_tef", null=True, blank=True,
    )
    venda = models.ForeignKey(
        "vendas.Venda", on_delete=models.PROTECT, related_name="transacoes_tef", null=True, blank=True,
    )
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    forma = models.CharField(max_length=10, choices=FORMA_CHOICES, default="credito")
    parcelas = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    # Id da cobrança no provedor (pra consultar/cancelar); sandbox = "SANDBOX-...".
    id_externo = models.CharField(max_length=80, blank=True)
    # Requisição de estorno aberta na maquininha (Vero: o operador conclui no terminal).
    id_estorno = models.CharField(max_length=80, blank=True)

    adquirente = models.CharField("Adquirente/banco", max_length=60, blank=True)
    terminal_codigo = models.CharField("Código de terminal", max_length=30, blank=True)
    bandeira = models.CharField(max_length=30, blank=True)
    nsu = models.CharField(max_length=40, blank=True)
    codigo_autorizacao = models.CharField(max_length=40, blank=True)
    # Vai pro grupo de cartão da NFC-e (CNPJ da credenciadora), junto com bandeira e autorização.
    cnpj_credenciadora = models.CharField(max_length=18, blank=True)
    mensagem_erro = models.CharField(max_length=300, blank=True)

    # Sem FK — Usuario vive no schema public (mesmo motivo de AuditLog/MovimentoEstoque).
    usuario_id = models.UUIDField(null=True, blank=True)
    usuario_nome = models.CharField(max_length=150, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Transação TEF"
        verbose_name_plural = "Transações TEF"

    def __str__(self):
        return f"TEF {self.get_status_display()} · R$ {self.valor} · {self.get_forma_display()}"


class NotaFiscalEmitida(models.Model):
    """Nota emitida pelo backend de apps.pagamentos.notas (simulação enquanto
    não há conta Focus NFe). O XML autorizado e o de cancelamento ficam
    guardados aqui pra exportação mensal à contabilidade."""

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
    recebimento = models.ForeignKey(
        "financeiro.Recebimento", on_delete=models.PROTECT, related_name="notas_fiscais", null=True, blank=True,
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
    # 44 dígitos na NFC-e, 50 na NFS-e Nacional.
    chave_acesso = models.CharField(max_length=50, blank=True)
    # NFS-e Nacional: Id da DPS enviada e ainda sem resposta — a próxima
    # tentativa consulta essa DPS antes de mandar outra (não duplica a nota).
    id_dps = models.CharField(max_length=45, blank=True)
    # Snapshot do que foi enviado ao emissor (prestador, tomador, itens, totais).
    dados = models.JSONField(default=dict, blank=True)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    url_pdf = models.URLField(blank=True)
    url_xml = models.URLField(blank=True)
    # XMLs guardados no próprio Vettro (contador: guardar os autorizados e os de
    # cancelamento e exportar pra contabilidade — ver apps.pagamentos.contabilidade).
    xml = models.TextField("XML autorizado", blank=True)
    xml_cancelamento = models.TextField("XML do cancelamento", blank=True)
    mensagem_erro = models.CharField(max_length=500, blank=True)
    emitida_em = models.DateTimeField(null=True, blank=True)
    emitida_por_nome = models.CharField(max_length=150, blank=True)
    cancelada_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Nota fiscal emitida"
        verbose_name_plural = "Notas fiscais emitidas"

    def __str__(self):
        return f"{self.get_tipo_display()} {self.numero or '(sem número)'}"

    @property
    def aviso_sem_valor(self) -> str:
        """"SIMULAÇÃO" (emissor de teste do Vettro), "HOMOLOGAÇÃO" (Emissor
        Nacional de teste) ou "" (nota real)."""
        if not self.simulacao:
            return ""
        return "HOMOLOGAÇÃO" if self.dados.get("emissor", {}).get("ambiente") == "homologacao" else "SIMULAÇÃO"
