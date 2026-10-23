from django import forms

from apps.core.campos import TelefoneField
from apps.pacientes.models import Paciente

from . import services
from .models import Agendamento, BloqueioAgenda, Consultorio


class AgendamentoForm(forms.ModelForm):
    tutor_tel = TelefoneField(required=False)
    paciente = forms.ModelChoiceField(queryset=Paciente.objects.all(), required=False)
    consultorio = forms.ModelChoiceField(queryset=Consultorio.objects.filter(ativo=True), required=False)

    class Meta:
        model = Agendamento
        fields = [
            "paciente", "consultorio", "data", "hora", "pac_nome", "tutor_nome", "tutor_tel",
            "queixa", "servicos_livre", "encaixe", "obs",
        ]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "hora": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "obs": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, clinica_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.clinica_id = clinica_id
        self.conflitos = []

    def duracao_dos_servicos(self) -> int:
        from django.db.models import Sum

        from apps.financeiro.models import Servico

        from apps.financeiro.models import TipoExame

        def ids(campo):
            valores = self.data.getlist(campo) if hasattr(self.data, "getlist") else self.data.get(campo, [])
            return [i for i in valores if i]

        total = (Servico.objects.filter(pk__in=ids("servico_ids")).aggregate(t=Sum("duracao_min"))["t"] or 0) \
            + (TipoExame.objects.filter(pk__in=ids("exame_ids")).aggregate(t=Sum("duracao_min"))["t"] or 0)
        return total or services.config_agenda()["intervalo"]

    def clean(self):
        dados = super().clean()
        if not dados.get("paciente") and not dados.get("pac_nome"):
            raise forms.ValidationError("Informe um paciente cadastrado ou o nome do paciente avulso.")

        data, hora = dados.get("data"), dados.get("hora")
        # Duração = soma dos serviços marcados (cada serviço tem a sua, em Serviços);
        # sem serviço, o intervalo padrão da grade.
        duracao = self.duracao_dos_servicos()
        self.instance.duracao_min = duracao
        consultorio = dados.get("consultorio")
        if data:
            hora_fim = None
            if hora:
                from datetime import datetime, timedelta

                hora_fim = (datetime.combine(data, hora) + timedelta(minutes=duracao)).time()
            bloqueio = services.bloqueio_que_cobre(
                data, hora, hora_fim, consultorio_id=consultorio.pk if consultorio else None,
            )
            if bloqueio:
                raise forms.ValidationError(
                    f"{bloqueio.alvo} está com a agenda fechada em {data:%d/%m/%Y} "
                    f"({bloqueio.descricao_faixa()}): {bloqueio.motivo}."
                )
            self.conflitos = services.conflitos(
                data, hora, duracao, consultorio_id=consultorio.pk if consultorio else None,
                excluir_id=self.instance.pk if self.instance else None,
            )
            if self.conflitos and not dados.get("encaixe"):
                outros = ", ".join(f"{a.hora:%H:%M} {a.pac_nome}" for a in self.conflitos[:3])
                raise forms.ValidationError(
                    f"Esse horário já está ocupado no {consultorio.nome} ({outros}). "
                    "Escolha outro horário ou marque \"Encaixe\"."
                )
        return dados


class ConsultorioForm(forms.ModelForm):
    class Meta:
        model = Consultorio
        fields = ["nome", "endereco", "ativo"]


def _hora(h) -> str:
    """time(9, 0) -> "9h"; time(12, 30) -> "12h30"."""
    return f"{h.hour}h" + (f"{h.minute:02d}" if h.minute else "")


class BloqueioForm(forms.ModelForm):
    consultorio = forms.ModelChoiceField(
        queryset=Consultorio.objects.filter(ativo=True), required=False,
        empty_label="Todos os consultórios (bloqueio geral)",
    )

    class Meta:
        model = BloqueioAgenda
        fields = ["consultorio", "data_inicio", "data_fim", "turno", "hora_inicio", "hora_fim",
                  "recorrente", "dia_semana", "motivo"]
        widgets = {
            "data_inicio": forms.DateInput(attrs={"type": "date"}),
            "data_fim": forms.DateInput(attrs={"type": "date"}),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}),
            "hora_fim": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, clinica_id=None, **kwargs):
        from apps.core.models import ConfiguracaoClinica

        super().__init__(*args, **kwargs)
        self.clinica_id = clinica_id
        # Turnos e horários dentro do expediente da clínica (Clínica → Agenda).
        config = ConfiguracaoClinica.atual()
        self.abre, self.fecha = config.agenda_hora_inicio, config.agenda_hora_fim
        rotulos = {
            BloqueioAgenda.TURNO_MANHA: f"Manhã ({_hora(self.abre)}–12h)",
            BloqueioAgenda.TURNO_TARDE: f"Tarde (12h–{_hora(self.fecha)})",
        }
        self.fields["turno"].choices = [(v, rotulos.get(v, r)) for v, r in BloqueioAgenda.TURNO_CHOICES]
        for campo in ("hora_inicio", "hora_fim"):
            self.fields[campo].widget.attrs.update({"min": self.abre.strftime("%H:%M"), "max": self.fecha.strftime("%H:%M"), "step": 300})

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get("data_inicio"), dados.get("data_fim")
        recorrente = dados.get("recorrente")

        if recorrente:
            if dados.get("dia_semana") in (None, ""):
                raise forms.ValidationError("Selecione o dia da semana pro bloqueio recorrente.")
            if not inicio:
                raise forms.ValidationError("Informe a data de início da recorrência.")
        elif not fim:
            raise forms.ValidationError("Informe a data final (ou marque \"Repetir toda semana\").")

        if inicio and fim and fim < inicio:
            raise forms.ValidationError("Data final não pode ser antes da data inicial.")
        if dados.get("turno") == BloqueioAgenda.TURNO_HORARIO:
            h_ini, h_fim = dados.get("hora_inicio"), dados.get("hora_fim")
            if not (h_ini and h_fim):
                raise forms.ValidationError("Informe o horário de início e de fim do bloqueio.")
            if h_fim <= h_ini:
                raise forms.ValidationError("O horário final do bloqueio precisa ser depois do inicial.")
            if h_ini < self.abre or h_fim > self.fecha:
                raise forms.ValidationError(
                    f"O horário precisa estar dentro do funcionamento da clínica ({_hora(self.abre)} às {_hora(self.fecha)})."
                )
        return dados

    def save(self, commit=True):
        bloqueio = super().save(commit=False)
        if bloqueio.turno != BloqueioAgenda.TURNO_HORARIO:
            bloqueio.hora_inicio = bloqueio.hora_fim = None
        if commit:
            bloqueio.save()
        return bloqueio

