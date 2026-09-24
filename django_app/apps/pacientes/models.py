import uuid
from datetime import date, time

from django.db import models

from apps.core.storage import TenantFileSystemStorage
from apps.core.validators import TamanhoArquivoValidator

ESPECIE_CHOICES = [("cao", "Cão"), ("gato", "Gato"), ("outro", "Outro")]

VACINA_VERME_CHOICES = [
    ("em_dia", "Em dia"), ("atrasada", "Atrasada"),
    ("nao", "Não"), ("desconhecido", "Desconhecido"),
]
RUA_CHOICES = [("sim", "Sim"), ("nao", "Não"), ("controlado", "Controlado")]
CONVIVE_CHOICES = [("sim", "Sim"), ("nao", "Não")]
ALIMENTACAO_CHOICES = [
    ("racao_seca", "Ração seca"), ("racao_umida", "Ração úmida"),
    ("mista", "Mista"), ("natural", "Natural"), ("outro", "Outro"),
]


class Paciente(models.Model):
    """Porte direto de backend/app/models.py:Paciente (ver §3 do plano).
    tutor é SET_NULL — excluir o tutor não apaga os pacientes vinculados,
    eles ficam órfãos (mesmo comportamento do sistema atual)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tutor = models.ForeignKey(
        "tutores.Tutor", on_delete=models.SET_NULL, null=True, blank=True, related_name="pacientes"
    )
    nome = models.CharField(max_length=150)
    especie = models.CharField(max_length=10, choices=ESPECIE_CHOICES)
    raca = models.CharField(max_length=100, blank=True)
    peso = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    data_nascimento = models.DateField(null=True, blank=True)
    obs = models.TextField("Observações", blank=True)
    foto_perfil = models.ImageField(
        upload_to="pacientes/fotos_perfil/",
        storage=TenantFileSystemStorage(),
        null=True,
        blank=True,
        validators=[TamanhoArquivoValidator(3 * 1024 * 1024, "Foto de perfil")],
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    @property
    def especie_emoji(self) -> str:
        return {"cao": "🐶", "gato": "🐱"}.get(self.especie, "🐾")

    @property
    def idade_texto(self) -> str:
        if not self.data_nascimento:
            return "—"
        from datetime import date

        hoje = date.today()
        anos = hoje.year - self.data_nascimento.year
        meses = hoje.month - self.data_nascimento.month
        if hoje.day < self.data_nascimento.day:
            meses -= 1
        if meses < 0:
            anos -= 1
            meses += 12
        partes = []
        if anos:
            partes.append(f"{anos} ano{'s' if anos != 1 else ''}")
        if meses or not partes:
            partes.append(f"{meses} mes{'es' if meses != 1 else ''}")
        return " e ".join(partes)


class Nota(models.Model):
    """Aba 📝 Anotações da Ficha — porte de backend/app/models.py:Nota."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name="notas")
    titulo = models.CharField(max_length=150, blank=True)
    conteudo = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)
    editado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return self.titulo or "Sem título"


class AnamneseHist(models.Model):
    """Aba 🩺 Anamnese — porte de backend/app/models.py:AnamneseHist. Campos
    av_* são a avaliação física (vitals). servicos/insumos são snapshots
    JSONField, não FK (§3 do plano)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name="anamneses")
    data = models.DateField(default=date.today)
    hora = models.TimeField(default=time)

    queixa = models.TextField("Queixa principal", blank=True)
    historico = models.TextField("Histórico clínico anterior", blank=True)
    medicamentos = models.TextField("Medicamentos em uso", blank=True)
    alergias = models.TextField("Alergias conhecidas", blank=True)
    obs_add = models.TextField("Observações adicionais", blank=True)
    alimentacao = models.CharField(max_length=20, choices=ALIMENTACAO_CHOICES, blank=True)
    vacina = models.CharField("Vacinação", max_length=20, choices=VACINA_VERME_CHOICES, blank=True)
    verme = models.CharField("Vermifugação", max_length=20, choices=VACINA_VERME_CHOICES, blank=True)
    rua = models.CharField("Acesso à rua", max_length=20, choices=RUA_CHOICES, blank=True)
    convive = models.CharField("Convive com outros animais", max_length=10, choices=CONVIVE_CHOICES, blank=True)

    av_fc = models.CharField("FC (bpm)", max_length=30, blank=True)
    av_fr = models.CharField("FR (mpm)", max_length=30, blank=True)
    av_pa = models.CharField("PA (mmHg)", max_length=30, blank=True)
    av_temp = models.CharField("Temperatura (°C)", max_length=30, blank=True)
    av_hidratacao = models.CharField("Hidratação", max_length=60, blank=True)
    av_mucosas = models.CharField("Mucosas", max_length=60, blank=True)
    av_linf_sub = models.CharField("Linfonodos submandibulares", max_length=60, blank=True)
    av_linf_sube = models.CharField("Linfonodos subescapulares", max_length=60, blank=True)
    av_linf_ing = models.CharField("Linfonodos inguinais", max_length=60, blank=True)
    av_linf_pop = models.CharField("Linfonodos poplíteos", max_length=60, blank=True)
    av_demais = models.TextField("Demais informações", blank=True)

    servicos = models.JSONField(default=list, blank=True)
    insumos = models.JSONField(default=list, blank=True)
    plantao = models.BooleanField(default=False)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name_plural = "Anamneses"


class CirurgiaHist(models.Model):
    """Aba 🔪 Cirurgias — porte de backend/app/models.py:CirurgiaHist. Preço
    dos procedimentos já vem resolvido pela faixa de peso do paciente
    (apps.financeiro.services.valor_por_peso) no momento da criação."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name="cirurgias")
    data = models.DateField(default=date.today)
    hora = models.TimeField(default=time)

    proc = models.CharField("Procedimento", max_length=200)
    clinica = models.CharField("Clínica/local", max_length=150, blank=True)
    anestesista = models.CharField(max_length=150, blank=True)
    desc_cir = models.TextField("Descrição da cirurgia", blank=True)
    pos_op = models.TextField("Pós-operatório", blank=True)

    procedimentos = models.JSONField(default=list, blank=True)
    insumos = models.JSONField(default=list, blank=True)
    plantao = models.BooleanField(default=False)
    outra_cidade = models.BooleanField("Deslocamento (outra cidade)", default=False)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name_plural = "Cirurgias"


class Exame(models.Model):
    """Aba 📄 Exames — antes base64 em TEXT, agora FileField real (§3 do
    plano, melhoria deliberada)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name="exames")
    nome = models.CharField(max_length=200)
    arquivo = models.FileField(
        upload_to="pacientes/exames/",
        storage=TenantFileSystemStorage(),
        validators=[TamanhoArquivoValidator(5 * 1024 * 1024, "Exame")],
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return self.nome

    @property
    def tamanho_mb(self) -> str:
        try:
            return f"{self.arquivo.size / (1024 * 1024):.1f} MB"
        except (ValueError, OSError):
            return "—"


class Foto(models.Model):
    """Aba 🖼️ Fotos — antes base64 em TEXT, agora ImageField real."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name="fotos")
    nome = models.CharField(max_length=200, blank=True)
    imagem = models.ImageField(
        upload_to="pacientes/fotos/",
        storage=TenantFileSystemStorage(),
        validators=[TamanhoArquivoValidator(4 * 1024 * 1024, "Foto")],
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
