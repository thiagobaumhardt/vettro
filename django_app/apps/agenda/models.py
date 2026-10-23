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
    """"Fechar a agenda" num período, dia inteiro ou só um turno — só o admin
    da clínica pode criar (@admin_required nas views, ver
    apps/agenda/views.py). Nenhum agendamento pode ser criado/reagendado pra
    dentro da janela bloqueada naquele consultório+turno (validação em
    AgendamentoForm.clean).

    `consultorio=None` é um bloqueio **geral** (fecha a agenda inteira, todos
    os consultórios de uma vez) — equivalente ao "bloqueio geral" do
    SimplesVet, que afeta todas as filas de atendimento. Sem isso, fechar a
    clínica inteira exigia criar um bloqueio manual em cada consultório.

    `recorrente=True` repete o bloqueio toda semana no mesmo `dia_semana`
    (0=segunda...6=domingo, igual `date.weekday()`), a partir de
    `data_inicio`, indefinidamente se `data_fim` ficar em branco —
    equivalente ao bloqueio recorrente do SimplesVet (ex: folga fixa toda
    quarta, sem precisar recriar toda semana)."""

    TURNO_DIA_INTEIRO = "dia_inteiro"
    TURNO_MANHA = "manha"
    TURNO_TARDE = "tarde"
    TURNO_NOITE = "noite"
    TURNO_HORARIO = "horario"
    # Manhã = abertura até 12h; tarde = 12h até o fechamento da clínica (o
    # formulário mostra a faixa real, ex.: "Tarde (12h–19h)"). "Noite" saiu
    # (2026-10): com a clínica aberta até 19h, a tarde fixa até 18h deixava a
    # última hora de fora. Fica só pra ler bloqueio antigo.
    TURNO_CHOICES = [
        (TURNO_DIA_INTEIRO, "Dia inteiro"),
        (TURNO_MANHA, "Manhã (até 12h)"),
        (TURNO_TARDE, "Tarde (a partir das 12h)"),
        (TURNO_HORARIO, "Horário específico"),
    ]
    # Faixas de horário de cada turno, usadas pra saber se um agendamento
    # (com hora marcada) cai dentro do turno bloqueado.
    FAIXAS_HORARIO = {
        TURNO_MANHA: (time(0, 0), time(11, 59, 59)),
        TURNO_TARDE: (time(12, 0), time(23, 59, 59)),
        TURNO_NOITE: (time(18, 0), time(23, 59, 59)),
    }

    DIA_SEMANA_CHOICES = [
        (0, "Segunda"), (1, "Terça"), (2, "Quarta"), (3, "Quinta"),
        (4, "Sexta"), (5, "Sábado"), (6, "Domingo"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    consultorio = models.ForeignKey(
        Consultorio, on_delete=models.CASCADE, related_name="bloqueios",
        null=True, blank=True,
        help_text="Em branco = bloqueio geral (fecha a agenda inteira, todos os consultórios).",
    )
    data_inicio = models.DateField()
    data_fim = models.DateField(
        null=True, blank=True,
        help_text="Em branco só é permitido em bloqueio recorrente (sem data de término).",
    )
    turno = models.CharField(max_length=15, choices=TURNO_CHOICES, default=TURNO_DIA_INTEIRO)
    # Só com turno="horario" (ex.: almoço 12:00–13:00).
    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fim = models.TimeField(null=True, blank=True)
    recorrente = models.BooleanField("Repetir toda semana", default=False)
    dia_semana = models.IntegerField(
        "Dia da semana", choices=DIA_SEMANA_CHOICES, null=True, blank=True,
        help_text="Obrigatório se o bloqueio for recorrente.",
    )
    motivo = models.CharField(max_length=200)
    criado_por_nome = models.CharField(max_length=150, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data_inicio"]

    @property
    def alvo(self) -> str:
        return self.consultorio.nome if self.consultorio_id else "Toda a clínica"

    @property
    def faixa(self) -> tuple | None:
        """(hora_inicio, hora_fim) que o bloqueio fecha no dia; None = dia inteiro."""
        if self.turno == self.TURNO_DIA_INTEIRO:
            return None
        if self.turno == self.TURNO_HORARIO:
            return (self.hora_inicio, self.hora_fim)
        return self.FAIXAS_HORARIO[self.turno]

    def descricao_faixa(self) -> str:
        if self.turno == self.TURNO_HORARIO and self.hora_inicio and self.hora_fim:
            return f"{self.hora_inicio:%H:%M}–{self.hora_fim:%H:%M}"
        return self.get_turno_display()

    def __str__(self):
        alvo = self.alvo
        if self.recorrente:
            return f"{alvo} fechado toda(o) {self.get_dia_semana_display()} ({self.get_turno_display()})"
        return f"{alvo} fechado {self.data_inicio}–{self.data_fim} ({self.get_turno_display()})"

    def cobre(self, data, hora=None, hora_fim=None) -> bool:
        """Se `hora` não for informada (agendamento sem horário definido),
        qualquer bloqueio na data já conta como conflito. Com `hora_fim`, testa
        se o intervalo [hora, hora_fim) encosta na faixa bloqueada."""
        if self.recorrente:
            if data < self.data_inicio:
                return False
            if self.data_fim and data > self.data_fim:
                return False
            if data.weekday() != self.dia_semana:
                return False
        elif not (self.data_inicio <= data <= self.data_fim):
            return False

        faixa = self.faixa
        if faixa is None or hora is None:
            return True
        inicio, fim = faixa
        if inicio is None or fim is None:
            return True
        if hora_fim is None:
            return inicio <= hora < fim if self.turno == self.TURNO_HORARIO else inicio <= hora <= fim
        return hora < fim and hora_fim > inicio  # sobreposição de intervalos


class Agendamento(models.Model):
    """Porte de backend/app/models.py:Agendamento. paciente é opcional —
    aceita tanto paciente cadastrado quanto avulso (nome livre), igual hoje.

    Agenda no estilo SimplesVet (2026-10): veterinário responsável (escala),
    duração, tipo de atendimento (etiqueta de cor), encaixe e
    ordem de chegada com os
    tempos de espera/atendimento (chegada_em → inicio_atendimento_em →
    fim_atendimento_em). As chaves antigas "agendado"/"realizado" continuam."""

    STATUS_CHOICES = [
        ("agendado", "Agendado"),
        ("aguardando", "Aguardando (chegou)"), ("em_atendimento", "Em atendimento"),
        ("realizado", "Atendido"), ("cancelado", "Cancelado"),
    ]
    STATUS_ATIVOS = ("agendado", "aguardando", "em_atendimento", "realizado")  # ocupam a agenda
    STATUS_ENCERRADOS = ("realizado", "cancelado")
    # Cancelar exige motivo (lista + texto livre). Cancelado libera o horário pra outro agendamento.
    MOTIVOS_CANCELAMENTO = [
        "Faltou (não compareceu)", "Tutor desmarcou", "Remarcado para outra data",
        "Paciente sem condições / óbito", "Clínica cancelou",
    ]

    # Etiqueta de cor = tipo de atendimento (mesmos tipos de atendimentos.Atendimento.Tipo).
    ETIQUETA_CHOICES = [
        ("consulta", "Consulta"), ("retorno", "Retorno"), ("ambulatorial", "Ambulatorial"),
        ("emergencia", "Emergência"), ("vacinacao", "Vacinação"),
        ("aplicacao_medicacao", "Aplicação de medicação"), ("curativo", "Curativo"), ("exame", "Exame"),
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
    duracao_min = models.PositiveSmallIntegerField("Duração (min)", default=30)
    etiqueta = models.CharField("Tipo de atendimento", max_length=20, choices=ETIQUETA_CHOICES, blank=True)
    encaixe = models.BooleanField(default=False, help_text="Agendado por cima de outro horário ocupado.")
    chegada_em = models.DateTimeField(null=True, blank=True)
    inicio_atendimento_em = models.DateTimeField(null=True, blank=True)
    fim_atendimento_em = models.DateTimeField(null=True, blank=True)
    pac_nome = models.CharField(max_length=150)
    tutor_nome = models.CharField(max_length=150, blank=True)
    tutor_tel = models.CharField(max_length=20, blank=True)
    queixa = models.CharField(max_length=300, blank=True)
    servicos = models.JSONField(default=list, blank=True)
    servicos_livre = models.CharField("Outros serviços", max_length=300, blank=True)
    # Exames escolhidos (tabela tipos_exames), em snapshot: [{"id", "nome", "duracao_min"}].
    exames = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="agendado")
    obs = models.TextField(blank=True)
    motivo_cancelamento = models.CharField("Motivo do cancelamento", max_length=200, blank=True)
    cancelado_em = models.DateTimeField(null=True, blank=True)
    cancelado_por_nome = models.CharField(max_length=150, blank=True)
    lembrete_enviado_em = models.DateTimeField(
        null=True, blank=True,
        help_text="Preenchido pelo comando enviar_lembretes_whatsapp — evita reenvio duplicado.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agenda"  # nome de negócio (padrão MKSaúde), em vez de agenda_agendamento
        ordering = ["data", "hora"]

    def __str__(self):
        return f"{self.pac_nome} · {self.data}"

    @property
    def hora_fim(self):
        if not self.hora:
            return None
        from datetime import datetime, timedelta

        return (datetime.combine(self.data, self.hora) + timedelta(minutes=self.duracao_min or 30)).time()

    @property
    def atrasado(self) -> bool:
        """Passou do horário e o paciente ainda não chegou (status Agendado). Não é gravado:
        vale enquanto ninguém marcar Chegou/Iniciar ou cancelar."""
        if self.status != "agendado" or not self.hora:
            return False
        from datetime import datetime

        from django.utils import timezone

        return timezone.localtime() > timezone.make_aware(datetime.combine(self.data, self.hora))

    @property
    def status_exibido(self) -> tuple[str, str]:
        """(classe, rótulo) pra tela — "Atrasado" sobrepõe "Agendado"."""
        return ("atrasado", "Atrasado") if self.atrasado else (self.status, self.get_status_display())

    @property
    def tipo_cor(self) -> str:
        """Tipo (cor) do agendamento: o do 1º serviço que tiver tipo; senão a etiqueta antiga."""
        return (next((s["tipo"] for s in self.servicos or [] if s.get("tipo")), "")
                or ("exame" if self.exames else "") or self.etiqueta)

    @property
    def espera_min(self) -> int | None:
        """Minutos entre a chegada e o início do atendimento."""
        if self.chegada_em and self.inicio_atendimento_em:
            return max(0, round((self.inicio_atendimento_em - self.chegada_em).total_seconds() / 60))
        return None

    @property
    def atendimento_min(self) -> int | None:
        """Minutos de atendimento (início → fim)."""
        if self.inicio_atendimento_em and self.fim_atendimento_em:
            return max(0, round((self.fim_atendimento_em - self.inicio_atendimento_em).total_seconds() / 60))
        return None

