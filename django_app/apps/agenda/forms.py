from django import forms
from django.db.models import Q

from apps.pacientes.models import Paciente

from .models import Agendamento, BloqueioAgenda, Consultorio


class AgendamentoForm(forms.ModelForm):
    paciente = forms.ModelChoiceField(queryset=Paciente.objects.all(), required=False)
    consultorio = forms.ModelChoiceField(queryset=Consultorio.objects.filter(ativo=True), required=False)

    class Meta:
        model = Agendamento
        fields = [
            "paciente", "consultorio", "data", "hora", "pac_nome", "tutor_nome", "tutor_tel",
            "queixa", "servicos_livre", "status", "obs",
        ]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}),
            "hora": forms.TimeInput(attrs={"type": "time"}),
        }

    def clean(self):
        dados = super().clean()
        if not dados.get("paciente") and not dados.get("pac_nome"):
            raise forms.ValidationError("Informe um paciente cadastrado ou o nome do paciente avulso.")

        consultorio = dados.get("consultorio")
        data = dados.get("data")
        hora = dados.get("hora")
        if data:
            # Bloqueio geral (consultorio=None) vale pra qualquer agendamento,
            # com ou sem consultório selecionado — além do bloqueio específico
            # do consultório escolhido, se houver.
            filtro_alvo = Q(consultorio__isnull=True)
            if consultorio:
                filtro_alvo |= Q(consultorio=consultorio)
            candidatos = BloqueioAgenda.objects.filter(filtro_alvo, data_inicio__lte=data)
            bloqueio = next((b for b in candidatos if b.cobre(data, hora)), None)
            if bloqueio:
                alvo = bloqueio.consultorio.nome if bloqueio.consultorio_id else "A clínica"
                raise forms.ValidationError(
                    f"{alvo} está com a agenda fechada em {data:%d/%m/%Y} "
                    f"({bloqueio.get_turno_display()}): {bloqueio.motivo}."
                )
        return dados


class ConsultorioForm(forms.ModelForm):
    class Meta:
        model = Consultorio
        fields = ["nome", "endereco", "ativo"]


class BloqueioForm(forms.ModelForm):
    consultorio = forms.ModelChoiceField(
        queryset=Consultorio.objects.filter(ativo=True), required=False,
        empty_label="Todos os consultórios (bloqueio geral)",
    )

    class Meta:
        model = BloqueioAgenda
        fields = ["consultorio", "data_inicio", "data_fim", "turno", "recorrente", "dia_semana", "motivo"]
        widgets = {
            "data_inicio": forms.DateInput(attrs={"type": "date"}),
            "data_fim": forms.DateInput(attrs={"type": "date"}),
        }

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
        return dados
