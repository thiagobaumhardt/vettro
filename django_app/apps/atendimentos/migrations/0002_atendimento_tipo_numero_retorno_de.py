import django.db.models.deletion
from django.db import migrations, models


def numerar_existentes(apps, schema_editor):
    Atendimento = apps.get_model("atendimentos", "Atendimento")
    for n, atendimento in enumerate(Atendimento.objects.order_by("criado_em", "id"), start=1):
        atendimento.numero = n
        atendimento.save(update_fields=["numero"])


class Migration(migrations.Migration):

    dependencies = [
        ('atendimentos', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='atendimento',
            name='tipo',
            field=models.CharField(choices=[('consulta', 'Consulta'), ('retorno', 'Retorno'), ('ambulatorial', 'Ambulatorial'), ('emergencia', 'Emergência')], default='consulta', max_length=15),
        ),
        migrations.AddField(
            model_name='atendimento',
            name='retorno_de',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='retornos', to='atendimentos.atendimento'),
        ),
        migrations.AddField(
            model_name='atendimento',
            name='numero',
            field=models.PositiveIntegerField(editable=False, null=True),
        ),
        migrations.RunPython(numerar_existentes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='atendimento',
            name='numero',
            field=models.PositiveIntegerField(editable=False, unique=True),
        ),
    ]
