import uuid
from datetime import time

from django.db import models


class Consultorio(models.Model):
    """Recurso agendável cadastrado livremente pelo admin — pode ser uma
    sala física ("Sala de Exames"), uma unidade, ou até a agenda nomeada de
    uma profissional específica ("Consultório Franciele Vet"). O sistema não
    impõe categoria nenhuma, é só um nome + endereço opcional. O admin da
    clínica pode "fechar" a agenda de um desses num período (ver
    BloqueioAgenda) — não existe conceito equivalente confirmado no
    SimplesVet (que organiza por profissional), essa é uma decisão própria
    do Vettro pedida explicitamente pelo usuário."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(
        max_length=150,
        help_text='Livre — pode ser uma sala, uma unidade, ou o nome de uma profissional (ex: "Consultório Franciele Vet").',
    )
    endereco = models.CharField(max_length=200, blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class BloqueioAgenda(models.Model):
    """"Fechar a agenda" de um consultório num período, dia inteiro ou só um
    turno — só o admin da clínica pode criar (@admin_required nas views, ver
    apps/agenda/views.py). Nenhum agendamento pode ser criado/reagendado pra
    dentro da janela bloqueada naquele consultório+turno (validação em
    AgendamentoForm.clean)."""

    TURNO_DIA_INTEIRO = "dia_inteiro"
    TURNO_MANHA = "manha"
    TURNO_TARDE = "tarde"
    TURNO_NOITE = "noite"
    TURNO_CHOICES = [
        (TURNO_DIA_INTEIRO, "Dia inteiro"),
        (TURNO_MANHA, "Manhã (até 12h)"),
        (TURNO_TARDE, "Tarde (12h–18h)"),
        (TURNO_NOITE, "Noite (a partir das 18h)"),
    ]
    # Faixas de horário de cada turno, usadas pra saber se um agendamento
    # (com hora marcada) cai dentro do turno bloqueado.
    FAIXAS_HORARIO = {
        TURNO_MANHA: (time(0, 0), time(11, 59, 59)),
        TURNO_TARDE: (time(12, 0), time(17, 59, 59)),
        TURNO_NOITE: (time(18, 0), time(23, 59, 59)),
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    consultorio = models.ForeignKey(Consultorio, on_delete=models.CASCADE, related_name="bloqueios")
    data_inicio = models.DateField()
    data_fim = models.DateField()
    turno = models.CharField(max_length=15, choices=TURNO_CHOICES, default=TURNO_DIA_INTEIRO)
    motivo = models.CharField(max_length=200)
    criado_por_nome = models.CharField(max_length=150, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data_inicio"]

    def __str__(self):
        return f"{self.consultorio.nome} fechado {self.data_inicio}–{self.data_fim} ({self.get_turno_display()})"

    def cobre(self, data, hora=None) -> bool:
        """Se `hora` não for informada (agendamento sem horário definido),
        qualquer bloqueio na data já conta como conflito."""
        if not (self.data_inicio <= data <= self.data_fim):
            return False
        if self.turno == self.TURNO_DIA_INTEIRO or hora is None:
            return True
        inicio, fim = self.FAIXAS_HORARIO[self.turno]
        return inicio <= hora <= fim


class Agendamento(models.Model):
    """Porte de backend/app/models.py:Agendamento. paciente é opcional —
    aceita tanto paciente cadastrado quanto avulso (nome livre), igual hoje."""

    STATUS_CHOICES = [
        ("agendado", "Agendado"), ("confirmado", "Confirmado"),
        ("realizado", "Realizado"), ("cancelado", "Cancelado"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paciente = models.ForeignKey(
        "pacientes.Paciente", on_delete=models.SET_NULL, null=True, blank=True, related_name="agendamentos"
    )
    consultorio = models.ForeignKey(
        Consultorio, on_delete=models.SET_NULL, null=True, blank=True, related_name="agendamentos"
    )
    data = models.DateField()
    hora = models.TimeField(null=True, blank=True)
    pac_nome = models.CharField(max_length=150)
    tutor_nome = models.CharField(max_length=150, blank=True)
    tutor_tel = models.CharField(max_length=20, blank=True)
    queixa = models.CharField(max_length=300, blank=True)
    servicos = models.JSONField(default=list, blank=True)
    servicos_livre = models.CharField("Outros serviços", max_length=300, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="agendado")
    obs = models.TextField(blank=True)
    lembrete_enviado_em = models.DateTimeField(
        null=True, blank=True,
        help_text="Preenchido pelo comando enviar_lembretes_whatsapp — evita reenvio duplicado.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["data", "hora"]

    def __str__(self):
        return f"{self.pac_nome} · {self.data}"
