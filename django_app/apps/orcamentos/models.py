import uuid

from django.db import models


class Orcamento(models.Model):
    """Orçamento impresso pra um tutor — só estimativa: não gera Cobrança nem
    mexe no estoque. Itens em snapshot (JSON), como Atendimento/Cobrança."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Sequencial por clínica (mesmo esquema de Atendimento.numero).
    numero = models.PositiveIntegerField(unique=True, editable=False)
    tutor = models.ForeignKey("tutores.Tutor", on_delete=models.SET_NULL, null=True, blank=True, related_name="orcamentos")
    paciente = models.ForeignKey(
        "pacientes.Paciente", on_delete=models.SET_NULL, null=True, blank=True, related_name="orcamentos"
    )
    # Snapshots — limpos por apps.tutores.services.escrubar_snapshots_tutor.
    tutor_nome = models.CharField(max_length=150)
    tutor_tel = models.CharField(max_length=20, blank=True)
    pac_nome = models.CharField(max_length=150, blank=True)

    # [{"descricao": str, "qtd": int, "valor": "12.50"}]
    itens = models.JSONField(default=list)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valido_ate = models.DateField()
    obs = models.TextField("Observações", blank=True)

    usuario_nome = models.CharField(max_length=150, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Orçamento #{self.numero} · {self.tutor_nome}"

    @property
    def vencido(self) -> bool:
        from datetime import date

        return self.valido_ate < date.today()
