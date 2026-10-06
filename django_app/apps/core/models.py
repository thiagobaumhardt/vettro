from django.db import models

from .storage import TenantFileSystemStorage
from .validators import TamanhoArquivoValidator


class ConfiguracaoClinica(models.Model):
    """Dados da clínica usados em documentos impressos (orçamento). Vive no
    schema da clínica (1 linha só — ver `atual()`), editável pelo admin DA
    CLÍNICA em ⚙️ Clínica — diferente de plataforma.Clinica, que é da
    plataforma. Dados fiscais (CNPJ/IE/certificado) seguem fora de escopo."""

    razao_social = models.CharField("Razão social", max_length=200, blank=True)
    cnpj = models.CharField("CNPJ", max_length=18, blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    # Nomes iguais aos do Tutor pra reaproveitar a busca de CEP (tutores:cep_lookup).
    cep = models.CharField("CEP", max_length=9, blank=True)
    endereco = models.CharField("Rua", max_length=250, blank=True)
    numero = models.CharField("Número", max_length=20, blank=True)
    complemento = models.CharField(max_length=100, blank=True)
    bairro = models.CharField(max_length=100, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    uf = models.CharField("UF", max_length=2, blank=True)
    marca_dagua = models.ImageField(
        "Marca d'água / logo", upload_to="clinica/", storage=TenantFileSystemStorage(),
        null=True, blank=True, validators=[TamanhoArquivoValidator(2 * 1024 * 1024, "Marca d'água")],
        help_text="PNG com fundo transparente fica melhor. Sai bem clara no fundo do PDF e pequena no cabeçalho.",
    )

    # Regra fiscal da venda de produtos (NFC-e) — o contador passa estas
    # poucas linhas uma vez, em vez de códigos produto por produto. Os padrões
    # são os mais comuns pra Simples Nacional vendendo no balcão dentro do
    # estado; o contador confirma. Ver apps.estoque.fiscal.
    REGIME_CHOICES = [
        ("simples", "Simples Nacional"), ("mei", "MEI"),
        ("presumido", "Lucro Presumido"), ("real", "Lucro Real"),
    ]
    regime_tributario = models.CharField("Regime tributário", max_length=10, choices=REGIME_CHOICES, default="simples")
    cfop_venda = models.CharField("CFOP — produto normal", max_length=4, default="5102")
    cst_csosn_venda = models.CharField("CSOSN/CST — produto normal", max_length=4, default="102")
    cfop_venda_st = models.CharField("CFOP — produto com substituição tributária", max_length=4, default="5405")
    cst_csosn_venda_st = models.CharField("CSOSN/CST — produto com substituição tributária", max_length=4, default="500")

    validade_orcamento_dias = models.PositiveSmallIntegerField(
        "Validade padrão do orçamento (dias)", default=15,
    )

    def __str__(self):
        return "Configuração da clínica"

    @property
    def endereco_completo(self) -> str:
        """Ex: "Rua das Flores, 123 - Sala 2 - Centro - Porto Alegre/RS - CEP 90000-000"."""
        rua = ", ".join(filter(None, [self.endereco, self.numero]))
        cidade = "/".join(filter(None, [self.cidade, self.uf.upper()]))
        partes = [rua, self.complemento, self.bairro, cidade, f"CEP {self.cep}" if self.cep else ""]
        return " - ".join(p for p in partes if p)

    @classmethod
    def atual(cls) -> "ConfiguracaoClinica":
        config, _ = cls.objects.get_or_create(pk=1)
        return config


class PerfilProfissional(models.Model):
    """Dados de quem assina documentos (receita, atestado) NESTA clínica —
    CRMV e imagem da assinatura/carimbo. Sem FK pro Usuario (schema public,
    mesmo motivo do AuditLog); a pessoa edita o próprio em 👤 Meu perfil e o
    admin edita de qualquer um em 🔑 Usuários."""

    usuario_id = models.UUIDField(unique=True)
    nome_completo = models.CharField(max_length=150, blank=True, help_text="Como deve sair na assinatura.")
    crmv = models.CharField("CRMV", max_length=20, blank=True)
    crmv_uf = models.CharField("UF do CRMV", max_length=2, blank=True)
    # Registro no MAPA (sai no receituário de controle especial).
    mapa = models.CharField("Registro no MAPA", max_length=30, blank=True)
    assinatura = models.ImageField(
        "Assinatura / carimbo", upload_to="assinaturas/", storage=TenantFileSystemStorage(),
        null=True, blank=True, validators=[TamanhoArquivoValidator(2 * 1024 * 1024, "Assinatura")],
        help_text="Imagem PNG (de preferência com fundo transparente) da assinatura ou carimbo.",
    )

    # Contato e endereço do profissional (cadastro do veterinário).
    telefone = models.CharField("Telefone de contato", max_length=20, blank=True)
    cep = models.CharField("CEP", max_length=9, blank=True)
    endereco = models.CharField("Rua", max_length=250, blank=True)
    numero = models.CharField("Número", max_length=20, blank=True)
    complemento = models.CharField(max_length=100, blank=True)
    bairro = models.CharField(max_length=100, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    uf = models.CharField("UF", max_length=2, blank=True)
    # Só o admin da clínica edita (🔑 Usuários → Perfil); a pessoa só vê.
    data_admissao = models.DateField("Data de admissão", null=True, blank=True)

    def __str__(self):
        return self.nome_completo or str(self.usuario_id)

    @property
    def endereco_completo(self) -> str:
        rua = ", ".join(filter(None, [self.endereco, self.numero]))
        cidade = "/".join(filter(None, [self.cidade, self.uf.upper()]))
        partes = [rua, self.complemento, self.bairro, cidade, f"CEP {self.cep}" if self.cep else ""]
        return " - ".join(p for p in partes if p)

    @property
    def crmv_formatado(self) -> str:
        if not self.crmv:
            return ""
        return f"CRMV-{self.crmv_uf.upper()} {self.crmv}" if self.crmv_uf else f"CRMV {self.crmv}"

    @classmethod
    def de(cls, usuario) -> "PerfilProfissional":
        perfil, _ = cls.objects.get_or_create(
            usuario_id=usuario.id, defaults={"nome_completo": getattr(usuario, "nome", "")},
        )
        return perfil
