import uuid
from datetime import date, time, timedelta

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.pacientes.models import ESPECIE_CHOICES


class Vacina(models.Model):
    """Catálogo de vacinas da clínica — só o PROTOCOLO clínico (quantas doses,
    intervalo, reforço). Preço, lote, validade e quantidade ficam no Insumo
    vinculado, que é o que dá baixa no estoque quando a vacina é aplicada."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=100)
    especie = models.CharField(
        max_length=10, choices=ESPECIE_CHOICES, blank=True, help_text="Em branco = qualquer espécie."
    )
    doses_iniciais = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(3)],
        help_text="Quantas doses no protocolo inicial (1 a 3).",
    )
    intervalo_dias = models.PositiveSmallIntegerField(
        default=21, help_text="Dias entre as doses do protocolo inicial."
    )
    reforco_anual = models.BooleanField(default=True)
    insumo = models.ForeignKey(
        "estoque.Insumo", on_delete=models.SET_NULL, null=True, blank=True, related_name="vacinas",
        help_text="Item do estoque que sai quando a vacina é aplicada (1 unidade por dose).",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    def doses_disponiveis(self) -> list[str]:
        """Valores de Atendimento.Dose aplicáveis a esta vacina."""
        doses = [str(n) for n in range(1, self.doses_iniciais + 1)]
        if self.reforco_anual:
            doses.append(Atendimento.Dose.REFORCO.value)
        return doses

    def sugerir_proxima_dose(self, dose: str, data_aplicacao: date) -> date | None:
        """Data sugerida da próxima dose, ou None se o protocolo acabou
        (última dose inicial de vacina sem reforço anual)."""
        if dose != Atendimento.Dose.REFORCO and int(dose) < self.doses_iniciais:
            return data_aplicacao + timedelta(days=self.intervalo_dias)
        if self.reforco_anual:
            return data_aplicacao + timedelta(days=365)
        return None


class Atendimento(models.Model):
    """Módulo standalone de "atendimento rápido" — independente da Ficha do
    paciente (não é a mesma coisa que Anamnese). Porte de
    backend/app/models.py:Atendimento. Gera Cobrança pendente automática
    (igual Anamnese/Cirurgia) desde 2026-09 — ver services.criar_atendimento."""

    class Tipo(models.TextChoices):
        CONSULTA = "consulta", "Consulta"
        RETORNO = "retorno", "Retorno"
        AMBULATORIAL = "ambulatorial", "Ambulatorial"
        EMERGENCIA = "emergencia", "Emergência"
        VACINACAO = "vacinacao", "Vacinação"
        APLICACAO_MEDICACAO = "aplicacao_medicacao", "Aplicação de medicação"
        CURATIVO = "curativo", "Curativo"

    class Dose(models.TextChoices):
        PRIMEIRA = "1", "1ª dose"
        SEGUNDA = "2", "2ª dose"
        TERCEIRA = "3", "3ª dose"
        REFORCO = "reforco", "Anual"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Código legível do atendimento (o id é UUID). Sequencial por clínica —
    # cada clínica tem seu próprio schema, então a unicidade já é por tenant.
    # Atribuído em services.criar_atendimento.
    numero = models.PositiveIntegerField(unique=True, editable=False)
    tipo = models.CharField(max_length=25, choices=Tipo.choices, default=Tipo.CONSULTA)
    # Só preenchido quando tipo=retorno: o atendimento original que motivou o retorno.
    retorno_de = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="retornos"
    )
    # Só preenchidos quando tipo=vacinacao: a vacina (FK + nome em snapshot,
    # pro histórico sobreviver à exclusão do catálogo), a dose aplicada e a
    # data agendada pro retorno da próxima dose.
    vacina = models.ForeignKey(
        Vacina, on_delete=models.SET_NULL, null=True, blank=True, related_name="aplicacoes"
    )
    vacina_nome = models.CharField(max_length=100, blank=True)
    dose =models.CharField(max_length=10, choices=Dose.choices, blank=True)
    data_proxima_dose = models.DateField(null=True, blank=True)
    # Demais tipos (consulta/retorno/ambulatorial/emergência): data sugerida
    # pra o paciente voltar. Vacinação usa data_proxima_dose no lugar.
    data_retorno = models.DateField(null=True, blank=True)
    # Lembrete de WhatsApp: enviado `lembrete_dias_antes` dias antes da
    # data_alvo_lembrete pelo comando diário enviar_lembretes_whatsapp.
    # Em branco = sem lembrete.
    lembrete_dias_antes = models.PositiveSmallIntegerField(null=True, blank=True)
    lembrete_enviado_em = models.DateTimeField(null=True, blank=True)
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
        return f"#{self.numero} · {self.pac_nome} · {self.data}"

    @property
    def data_alvo_lembrete(self) -> date | None:
        return self.data_proxima_dose if self.tipo == self.Tipo.VACINACAO else self.data_retorno

    @property
    def data_lembrete(self) -> date | None:
        alvo = self.data_alvo_lembrete
        if alvo is None or self.lembrete_dias_antes is None:
            return None
        return alvo - timedelta(days=self.lembrete_dias_antes)
