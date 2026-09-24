from django import forms

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
        if consultorio and data:
            candidatos = BloqueioAgenda.objects.filter(
                consultorio=consultorio, data_inicio__lte=data, data_fim__gte=data,
            )
            bloqueio = next((b for b in candidatos if b.cobre(data, hora)), None)
            if bloqueio:
                raise forms.ValidationError(
                    f"{consultorio.nome} está com a agenda fechada em {data:%d/%m/%Y} "
                    f"({bloqueio.get_turno_display()}): {bloqueio.motivo}."
                )
        return dados


class ConsultorioForm(forms.ModelForm):
    class Meta:
        model = Consultorio
        fields = ["nome", "endereco", "ativo"]


class BloqueioForm(forms.ModelForm):
    class Meta:
        model = BloqueioAgenda
        fields = ["consultorio", "data_inicio", "data_fim", "turno", "motivo"]
        widgets = {
            "data_inicio": forms.DateInput(attrs={"type": "date"}),
            "data_fim": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get("data_inicio"), dados.get("data_fim")
        if inicio and fim and fim < inicio:
            raise forms.ValidationError("Data final não pode ser antes da data inicial.")
        return dados
