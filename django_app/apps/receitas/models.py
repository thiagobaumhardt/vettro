import uuid

from django.db import models

USO_CHOICES = [
    ("oral", "Uso oral"), ("topico", "Uso tópico"), ("otologico", "Uso otológico"),
    ("oftalmico", "Uso oftálmico"), ("nasal", "Uso nasal"),
]
FARMACIA_CHOICES = [("humana", "Farmácia humana"), ("veterinaria", "Farmácia veterinária"), ("manipulada", "Farmácia de manipulação")]


class Receita(models.Model):
    """Receita emitida na Ficha do paciente. Três tipos:
    - livre: só texto digitado;
    - simples: lista de medicamentos (`itens`);
    - controlada: igual à simples, mas o PDF sai em 2 vias (farmácia/tutor).
    Dados do veterinário e do paciente ficam em snapshot — a receita impressa
    não pode mudar se o cadastro mudar depois."""

    class Tipo(models.TextChoices):
        LIVRE = "livre", "Receita livre"
        SIMPLES = "simples", "Receita simples"
        CONTROLADA = "controlada", "Receita controlada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paciente = models.ForeignKey("pacientes.Paciente", on_delete=models.CASCADE, related_name="receitas")
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    texto = models.TextField(blank=True)  # tipo=livre
    # [{"uso", "medicamento", "farmacia", "concentracao", "periodicidade", "tempo_uso", "obs"}]
    itens = models.JSONField(default=list, blank=True)

    pac_nome = models.CharField(max_length=150)
    pac_especie = models.CharField(max_length=20, blank=True)
    pac_raca = models.CharField(max_length=100, blank=True)
    pac_idade = models.CharField(max_length=40, blank=True)
    pac_peso = models.CharField(max_length=20, blank=True)
    tutor_nome = models.CharField(max_length=150, blank=True)
    tutor_endereco = models.CharField(max_length=300, blank=True)
    # Desde 2026-10 (layout do receituário): tutor_endereco guarda só rua/nº/compl./bairro
    # e a cidade vai em tutor_cidade_uf. Receitas antigas têm o endereço completo.
    tutor_cidade_uf = models.CharField(max_length=110, blank=True)
    tutor_cpf = models.CharField(max_length=14, blank=True)
    tutor_rg = models.CharField(max_length=20, blank=True)
    pac_sexo = models.CharField(max_length=10, blank=True)

    vet_usuario_id = models.UUIDField(null=True, blank=True)
    vet_nome = models.CharField(max_length=150, blank=True)
    vet_crmv = models.CharField(max_length=40, blank=True)
    vet_mapa = models.CharField(max_length=30, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.pac_nome} · {self.criado_em:%d/%m/%Y}"
