"""Roda uma vez por dia via cron externo (KingHost não tem Celery/worker
assíncrono disponível no plano compartilhado — um management command
agendado por cron é o padrão mais simples que funciona nesse hosting, ver
§11 do plano). Percorre as clínicas com o módulo de lembrete habilitado
(Clinica.modulo_whatsapp_lembrete — pedido explícito do usuário: desligado
por padrão, cada clínica liga quando tiver a Meta Business configurada)
verificando agendamentos de amanhã ainda sem lembrete enviado.

Além do módulo da clínica, agora também exige `Tutor.consentimento_whatsapp`
(LGPD — opt-in específico e revogável, separado do consentimento geral de
dados, já que a Meta Cloud API processa a mensagem fora do Brasil). Na
prática: agendamento avulso (sem Paciente cadastrado) ou paciente sem tutor
com consentimento marcado NUNCA recebe lembrete — não existe registro de
consentimento pra checar, então o padrão seguro é não enviar."""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django_tenants.utils import get_tenant_model, schema_context

from apps.agenda.models import Agendamento
from apps.agenda.notificacoes import get_backend, montar_mensagem_lembrete


class Command(BaseCommand):
    help = "Envia lembrete de WhatsApp 24h antes (no dia anterior) de cada agendamento, em todas as clínicas."

    def handle(self, *args, **options):
        amanha = date.today() + timedelta(days=1)
        backend = get_backend()
        Clinica = get_tenant_model()

        total_enviados = 0
        for clinica in Clinica.objects.exclude(schema_name="public").filter(modulo_whatsapp_lembrete=True):
            with schema_context(clinica.schema_name):
                agendamentos = (
                    Agendamento.objects.filter(data=amanha, lembrete_enviado_em__isnull=True)
                    .exclude(status="cancelado")
                    .exclude(tutor_tel="")
                    .select_related("paciente__tutor")
                )

                for agendamento in agendamentos:
                    tutor = agendamento.paciente.tutor if agendamento.paciente_id else None
                    if not (tutor and tutor.consentimento_whatsapp):
                        continue

                    mensagem = montar_mensagem_lembrete(agendamento)
                    if backend.enviar(agendamento.tutor_tel, mensagem):
                        agendamento.lembrete_enviado_em = timezone.now()
                        agendamento.save(update_fields=["lembrete_enviado_em"])
                        total_enviados += 1
                        self.stdout.write(
                            f"[{clinica.schema_name}] lembrete enviado: {agendamento.pac_nome} ({agendamento.tutor_tel})"
                        )

        self.stdout.write(self.style.SUCCESS(f"{total_enviados} lembrete(s) enviado(s)."))
