import uuid
from datetime import date, time

from django.db import models


class Atendimento(models.Model):
    """Módulo standalone de "atendimento rápido" — independente da Ficha do
    paciente (não é a mesma coisa que Anamnese). Porte de
    backend/app/models.py:Atendimento. NÃO gera Cobrança automática — essa
    assimetria em relação a Anamnese/Cirurgia é proposital, preservada do
    sistema atual (§9 do plano)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paciente = models.ForeignKey(
        "pacientes.Paciente", on_delete=models.SET_NULL, null=True, blank=True, related_name="atendimentos"
    )
    # Snapshots denormalizados do paciente/tutor no momento do atendimento —
    # não FK, pra manter o histórico estável mesmo se o paciente for editado
    # ou excluído depois.
    pac_nome = models.CharField(max_length=150)
    pac_especie = models.CharField(max_length=10, blank=True)
    tutor_nome = models.CharField(max_length=150, blank=True)
    tutor_tel = models.CharField(max_length=20, blank=True)

    data = models.DateField(default=date.today)
    hora = models.TimeField(default=time)
    servicos = models.JSONField(default=list, blank=True)
    insumos = models.JSONField(default=list, blank=True)
    plantao = models.BooleanField(default=False)
    obs = models.TextField(blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data", "-hora"]

    def __str__(self):
        return f"{self.pac_nome} · {self.data}"
