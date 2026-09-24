from django import forms

from apps.pacientes.models import Paciente


class AtendimentoForm(forms.Form):
    paciente = forms.ModelChoiceField(queryset=Paciente.objects.all())
    data = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    hora = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}))
    plantao = forms.BooleanField(required=False)
    obs = forms.CharField(required=False, widget=forms.Textarea)
