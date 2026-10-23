import os
import uuid
from datetime import time

from django.core.validators import FileExtensionValidator
from django.db import models

from .storage import TenantFileSystemStorage
from .validators import TamanhoArquivoValidator


class ConfiguracaoClinica(models.Model):
    """Dados da clínica usados em documentos impressos (orçamento). Vive no
    schema da clínica (1 linha só — ver `atual()`), editável pelo admin DA
    CLÍNICA em ⚙️ Clínica — diferente de plataforma.Clinica, que é da
    plataforma. Inclui os dados fiscais e o certificado A1 (cifrado) da NFS-e."""

    razao_social = models.CharField("Razão social", max_length=200, blank=True)
    cnpj = models.CharField("CNPJ", max_length=18, blank=True)
    # Vai como IE do emitente na NFC-e (RS: 10 dígitos, ex. 015/0197055).
    inscricao_estadual = models.CharField("Inscrição estadual", max_length=20, blank=True)
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
    # NFS-e: padrão de todos os serviços (cada serviço pode ter exceção no catálogo).
    nfse_codigo_tributacao_nacional = models.CharField(
        "Código de tributação nacional", max_length=6, default="050202",
        help_text="050202 = subitem 5.02 (clínicas e ambulatórios veterinários).",
    )
    nfse_codigo_municipal = models.CharField(
        "Código municipal", max_length=20, blank=True, help_text="Só se a prefeitura exigir um código próprio.",
    )
    # NFS-e direto no Emissor Nacional (apps.pagamentos.nfse_nacional). Com
    # certificado cadastrado a NFS-e vai pro Emissor Nacional; sem ele, simulação.
    codigo_municipio_ibge = models.CharField(
        "Código IBGE do município", max_length=7, blank=True, help_text="Preenchido pelo CEP (Cachoeira do Sul/RS = 4303004).",
    )
    inscricao_municipal = models.CharField("Inscrição municipal", max_length=15, blank=True)
    NFSE_AMBIENTE_CHOICES = [("homologacao", "Homologação (teste, sem valor fiscal)"), ("producao", "Produção (nota real)")]
    nfse_ambiente = models.CharField("Ambiente da NFS-e", max_length=12, choices=NFSE_AMBIENTE_CHOICES, default="homologacao")
    nfse_serie = models.CharField("Série da DPS", max_length=5, default="1")
    nfse_ultimo_dps = models.PositiveBigIntegerField("Último número de DPS", default=0)
    nfse_aliquota_simples = models.DecimalField(
        "Alíquota aproximada do Simples (%)", max_digits=4, decimal_places=2, null=True, blank=True,
        help_text="Percentual aproximado dos tributos no Simples Nacional, informado na nota. Varia com o faturamento — o contador passa todo mês.",
    )
    # Certificado A1 (.pfx) e senha cifrados (mesma cifra dos tokens do WhatsApp) —
    # quem tem os dois assina nota em nome da clínica.
    certificado_cifrado = models.TextField(blank=True)
    certificado_senha_cifrada = models.TextField(blank=True)
    certificado_titular = models.CharField(max_length=200, blank=True)
    certificado_validade = models.DateTimeField(null=True, blank=True)
    # Maquininha integrada (TEF): Vero = token que o app Vero Cliente PDV mostra ao abrir.
    tef_terminal_token = models.CharField("Token da maquininha", max_length=40, blank=True)

    validade_orcamento_dias = models.PositiveSmallIntegerField(
        "Validade padrão do orçamento (dias)", default=15,
    )

    # Agenda: faixa de horário mostrada nas visões Dia/Semana e usada pra
    # calcular os horários livres; intervalo = tamanho de cada linha da grade.
    agenda_hora_inicio = models.TimeField("Agenda abre às", default=time(8, 0))
    agenda_hora_fim = models.TimeField("Agenda fecha às", default=time(18, 0))
    # Estoque (análise automática): de quanto em quanto tempo a clínica faz compras.
    estoque_frequencia_compra_dias = models.PositiveSmallIntegerField(
        "Frequência de compras (dias)", default=30,
        help_text="De quanto em quanto tempo a clínica costuma comprar — usado na sugestão de compra.",
    )
    agenda_intervalo_min = models.PositiveSmallIntegerField(
        "Intervalo da grade (min)", default=30, choices=[(10, "10 min"), (15, "15 min"), (20, "20 min"), (30, "30 min"), (60, "60 min")],
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

    @property
    def tem_certificado(self) -> bool:
        return bool(self.certificado_cifrado)

    def certificado(self) -> tuple[bytes, str]:
        """(.pfx, senha) decifrados; (b"", "") sem certificado."""
        import base64

        from apps.whatsapp import cripto

        pfx = cripto.decifrar(self.certificado_cifrado)
        return (base64.b64decode(pfx) if pfx else b""), cripto.decifrar(self.certificado_senha_cifrada)

    def guardar_certificado(self, pfx: bytes, senha: str, *, titular: str, validade) -> None:
        import base64

        from apps.whatsapp import cripto

        self.certificado_cifrado = cripto.cifrar(base64.b64encode(pfx).decode()) if pfx else ""
        self.certificado_senha_cifrada = cripto.cifrar(senha) if pfx else ""
        self.certificado_titular, self.certificado_validade = (titular, validade) if pfx else ("", None)

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


def _caminho_documento_empresa(instancia, nome):
    # Nome aleatório no disco: o arquivo não é servido por /media/ (ver
    # core:documento_empresa); o nome original fica em `nome_arquivo`.
    return f"empresa/{uuid.uuid4().hex}{os.path.splitext(nome)[1].lower()}"


class DocumentoEmpresa(models.Model):
    """Documentos da própria clínica (contrato social, cartão CNPJ...), em
    Clínica → Documentos da empresa. Têm CPF e endereço das sócias: só o
    admin abre, por uma view protegida — nunca por link público de /media/."""

    TIPO_CHOICES = [
        ("contrato_social", "Contrato social"),
        ("cartao_cnpj", "Cartão CNPJ"),
        ("inscricao_estadual", "Inscrição estadual"),
        ("outro", "Outro"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descricao = models.CharField("Descrição", max_length=150, blank=True)
    arquivo = models.FileField(
        upload_to=_caminho_documento_empresa, storage=TenantFileSystemStorage(),
        validators=[TamanhoArquivoValidator(10 * 1024 * 1024, "Documento"),
                    FileExtensionValidator(["pdf", "png", "jpg", "jpeg"])],
    )
    nome_arquivo = models.CharField(max_length=200)
    enviado_por_nome = models.CharField(max_length=150, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["tipo", "-criado_em"]
        verbose_name = "Documento da empresa"
        verbose_name_plural = "Documentos da empresa"

    def __str__(self):
        return self.descricao or self.get_tipo_display()

    @property
    def tamanho_mb(self) -> str:
        try:
            return f"{self.arquivo.size / (1024 * 1024):.1f} MB"
        except (ValueError, OSError):
            return "—"
