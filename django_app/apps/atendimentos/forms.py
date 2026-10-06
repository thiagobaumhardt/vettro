from datetime import date, timedelta

from django import forms

from apps.pacientes.models import Paciente

from .models import Atendimento, Vacina

MAX_DIAS_LEMBRETE = 60


class VacinaForm(forms.ModelForm):
    class Meta:
        model = Vacina
        fields = ["nome", "especie", "doses_iniciais", "intervalo_dias", "reforco_anual", "insumo"]


class AtendimentoForm(forms.Form):
    tipo = forms.ChoiceField(
        choices=Atendimento.Tipo.choices, initial=Atendimento.Tipo.CONSULTA,
        widget=forms.Select(attrs={"x-model": "tipo"}),
    )
    paciente = forms.ModelChoiceField(
        queryset=Paciente.objects.all(), widget=forms.Select(attrs={"x-model": "pacienteId"})
    )
    # Campos condicionais abaixo são renderizados à mão no template (Alpine).
    retorno_de = forms.ModelChoiceField(queryset=Atendimento.objects.all(), required=False)
    vacina = forms.ModelChoiceField(queryset=Vacina.objects.all(), required=False)
    dose = forms.ChoiceField(choices=[("", "Selecione a dose")] + Atendimento.Dose.choices, required=False)
    data_proxima_dose = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    data_retorno = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    lembrete_dias_antes = forms.IntegerField(required=False, min_value=0, max_value=MAX_DIAS_LEMBRETE)
    data = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "x-model": "dataAtendimento", "x-on:change": "sugerirProxima()"}))
    hora = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}))
    plantao = forms.BooleanField(required=False)
    obs = forms.CharField(required=False, widget=forms.Textarea)

    def clean(self):
        dados = super().clean()
        if dados.get("tipo") == Atendimento.Tipo.VACINACAO:
            self._validar_vacinacao(dados)
            dados["data_retorno"] = None
            alvo, campo_alvo = dados.get("data_proxima_dose"), "data_proxima_dose"
        else:
            dados.update(vacina=None, dose="", data_proxima_dose=None)
            alvo, campo_alvo = dados.get("data_retorno"), "data_retorno"
            data = dados.get("data")
            if alvo is not None and data is not None and alvo <= data:
                self.add_error("data_retorno", "A data de retorno deve ser posterior à data do atendimento.")
        self._validar_lembrete(dados, alvo, campo_alvo)

        if dados.get("tipo") != Atendimento.Tipo.RETORNO:
            dados["retorno_de"] = None
            return dados
        origem, paciente = dados.get("retorno_de"), dados.get("paciente")
        if origem is None:
            self.add_error("retorno_de", "Informe o atendimento de origem do retorno.")
        elif paciente is not None and origem.paciente_id != paciente.pk:
            self.add_error("retorno_de", "O atendimento de origem é de outro paciente.")
        return dados

    def _validar_vacinacao(self, dados):
        vacina, dose, data = dados.get("vacina"), dados.get("dose"), dados.get("data")
        proxima, paciente = dados.get("data_proxima_dose"), dados.get("paciente")
        if vacina is None:
            self.add_error("vacina", "Informe a vacina aplicada.")
            return
        if paciente is not None and vacina.especie and vacina.especie != paciente.especie:
            self.add_error("vacina", f"A vacina {vacina.nome} não é indicada para {paciente.get_especie_display()}.")
            return
        if not dose:
            self.add_error("dose", "Informe a dose da vacina.")
            return
        if dose not in vacina.doses_disponiveis():
            self.add_error("dose", f"Dose inválida para o protocolo da vacina {vacina.nome}.")
            return
        # Próxima dose só é obrigatória se o protocolo ainda prevê uma.
        if proxima is None:
            if data is not None and vacina.sugerir_proxima_dose(dose, data) is not None:
                self.add_error("data_proxima_dose", "Informe a data da próxima dose da vacina.")
        elif data is not None and proxima <= data:
            self.add_error("data_proxima_dose", "A data da próxima dose deve ser posterior à data da vacinação.")

    def _validar_lembrete(self, dados, alvo, campo_alvo):
        """Lembrete só existe com data-alvo válida e não pode cair no passado."""
        if alvo is None or campo_alvo in self.errors:
            dados["lembrete_dias_antes"] = None
            return
        dias = dados.get("lembrete_dias_antes")
        if dias is not None and alvo - timedelta(days=dias) < date.today():
            self.add_error(
                "lembrete_dias_antes",
                f"Com {dias} dia(s) de antecedência o lembrete cairia numa data que já passou — diminua os dias.",
            )
