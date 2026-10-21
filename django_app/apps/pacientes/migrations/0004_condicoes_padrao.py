from django.db import migrations

CONDICOES_PADRAO = [
    "Cardiopata", "Diabético", "Renal crônico", "Epiléptico", "Alérgico",
    "Braquicefálico", "Idoso", "Gestante", "Agressivo",
]


def criar_condicoes_padrao(apps, schema_editor):
    CondicaoClinica = apps.get_model("pacientes", "CondicaoClinica")
    for nome in CONDICOES_PADRAO:
        CondicaoClinica.objects.get_or_create(nome=nome)


class Migration(migrations.Migration):
    """Roda em cada schema de clínica (inclusive as provisionadas depois),
    então toda clínica já começa com a lista padrão."""

    dependencies = [
        ('pacientes', '0003_condicao_clinica'),
    ]

    operations = [
        migrations.RunPython(criar_condicoes_padrao, migrations.RunPython.noop),
    ]
