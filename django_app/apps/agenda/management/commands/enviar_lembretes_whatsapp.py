"""Roda uma vez por dia via cron externo (KingHost não tem Celery/worker
assíncrono disponível no plano compartilhado — um management command
agendado por cron é o padrão mais simples que funciona nesse hosting, ver
§11 do plano). Percorre as clínicas com o módulo de lembrete habilitado
(Clinica.modulo_whatsapp_lembrete — pedido explícito do usuário: desligado
por padrão) e com o WhatsApp conectado em ⚙️ Clínica → WhatsApp, e envia
(templates aprovados na WABA da clínica — apps.whatsapp.modelos):

1. lembrete dos agendamentos de amanhã ainda sem lembrete enviado;
2. lembrete da próxima dose de vacina / do retorno de consulta,
   `Atendimento.lembrete_dias_antes` dias antes de `data_proxima_dose` /
   `data_retorno` (escolhido pelo vet no atendimento) — não envia se o
   paciente já voltou antes.

Além do módulo da clínica, agora também exige `Tutor.consentimento_whatsapp`
(LGPD — opt-in específico e revogável, separado do consentimento geral de
dados, já que a Meta Cloud API processa a mensagem fora do Brasil). Na
prática: agendamento avulso (sem Paciente cadastrado) ou paciente sem tutor
com consentimento marcado NUNCA recebe lembrete — não existe registro de
consentimento pra checar, então o padrão seguro é não enviar."""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db.models import DateField, Exists, ExpressionWrapper, F, OuterRef
from django.utils import timezone
from django_tenants.utils import get_tenant_model, schema_context

from apps.agenda.models import Agendamento
from apps.atendimentos.models import Atendimento
from apps.lembretes.models import MensagemWhatsApp
from apps.whatsapp import modelos, services as whatsapp


class Command(BaseCommand):
    help = "Envia os lembretes de WhatsApp do dia (agendamentos de amanhã e próximas doses de vacina), em todas as clínicas."

    def handle(self, *args, **options):
        hoje = date.today()
        amanha = hoje + timedelta(days=1)
        Clinica = get_tenant_model()

        total_enviados = 0
        for clinica in Clinica.objects.exclude(schema_name="public").filter(modulo_whatsapp_lembrete=True, ativa=True):
            if not whatsapp.pode_enviar(clinica.pk):
                self.stdout.write(f"[{clinica.schema_name}] WhatsApp não conectado — pulando.")
                continue
            with schema_context(clinica.schema_name):
                total_enviados += self._agendamentos(clinica, amanha)
                total_enviados += self._proximas_doses(clinica, hoje)
                total_enviados += self._retornos(clinica, hoje)

        self.stdout.write(self.style.SUCCESS(f"{total_enviados} lembrete(s) enviado(s)."))

    def _agendamentos(self, clinica, amanha) -> int:
        enviados = 0
        agendamentos = (
            Agendamento.objects.filter(data=amanha, lembrete_enviado_em__isnull=True)
            .exclude(status__in=["cancelado", "realizado"])
            .exclude(tutor_tel="")
            .select_related("paciente__tutor")
        )
        for agendamento in agendamentos:
            tutor = agendamento.paciente.tutor if agendamento.paciente_id else None
            if not (tutor and tutor.consentimento_whatsapp):
                continue
            mensagem = whatsapp.enviar(
                clinica.pk, telefone=agendamento.tutor_tel, modelo=modelos.AGENDAMENTO.nome, tutor=tutor,
                parametros=modelos.parametros_agendamento(agendamento, clinica.nome), tipo=MensagemWhatsApp.Tipo.AGENDAMENTO,
            )
            if mensagem.enviada:
                agendamento.lembrete_enviado_em = timezone.now()
                agendamento.save(update_fields=["lembrete_enviado_em"])
                enviados += 1
                self.stdout.write(f"[{clinica.schema_name}] lembrete enviado: {agendamento.pac_nome} ({agendamento.tutor_tel})")
        return enviados

    def _proximas_doses(self, clinica, hoje) -> int:
        """Lembrete da próxima dose de vacina — pula se o paciente já tomou
        uma dose mais nova da mesma vacina (voltou antes do lembrete)."""
        ja_voltou = Exists(Atendimento.objects.filter(
            paciente_id=OuterRef("paciente_id"), tipo=Atendimento.Tipo.VACINACAO,
            vacina_nome=OuterRef("vacina_nome"), data__gt=OuterRef("data"),
        ))
        pendentes = self._pendentes("data_proxima_dose", hoje).filter(tipo=Atendimento.Tipo.VACINACAO).exclude(ja_voltou)
        return self._enviar(clinica, pendentes, modelos.VACINA, modelos.parametros_vacina, MensagemWhatsApp.Tipo.VACINA)

    def _retornos(self, clinica, hoje) -> int:
        """Lembrete de retorno de consulta/ambulatorial/emergência/retorno —
        pula se já foi registrado um atendimento do tipo Retorno ligado a ele."""
        ja_voltou = Exists(Atendimento.objects.filter(retorno_de_id=OuterRef("pk")))
        pendentes = self._pendentes("data_retorno", hoje).exclude(tipo=Atendimento.Tipo.VACINACAO).exclude(ja_voltou)
        return self._enviar(clinica, pendentes, modelos.RETORNO, modelos.parametros_retorno, MensagemWhatsApp.Tipo.RETORNO)

    def _pendentes(self, campo_alvo, hoje):
        """Data do lembrete <= hoje e data-alvo ainda por vir: se o cron
        falhar num dia, o lembrete sai no dia seguinte em vez de se perder."""
        return (
            Atendimento.objects.filter(
                lembrete_enviado_em__isnull=True, lembrete_dias_antes__isnull=False, **{f"{campo_alvo}__gte": hoje},
            )
            .annotate(data_envio=ExpressionWrapper(
                F(campo_alvo) - F("lembrete_dias_antes") * timedelta(days=1), output_field=DateField(),
            ))
            .filter(data_envio__lte=hoje)
            .select_related("paciente__tutor")
        )

    def _enviar(self, clinica, atendimentos, modelo, parametros, tipo) -> int:
        enviados = 0
        for atendimento in atendimentos:
            tutor = atendimento.paciente.tutor if atendimento.paciente_id else None
            if not (tutor and tutor.consentimento_whatsapp and tutor.tel):
                continue
            mensagem = whatsapp.enviar(
                clinica.pk, telefone=tutor.tel, modelo=modelo.nome, tutor=tutor,
                parametros=parametros(atendimento, clinica.nome), tipo=tipo,
            )
            if mensagem.enviada:
                atendimento.lembrete_enviado_em = timezone.now()
                atendimento.save(update_fields=["lembrete_enviado_em"])
                enviados += 1
                self.stdout.write(f"[{clinica.schema_name}] {modelo.rotulo}: {atendimento.pac_nome} ({tutor.tel})")
        return enviados
