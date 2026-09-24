from django import forms

from .models import AnamneseHist, CirurgiaHist, Nota, Paciente


class PacienteForm(forms.ModelForm):
    class Meta:
        model = Paciente
        fields = ["tutor", "nome", "especie", "raca", "peso", "data_nascimento", "obs", "foto_perfil"]
        widgets = {
            "data_nascimento": forms.DateInput(attrs={"type": "date"}),
        }


class NotaForm(forms.ModelForm):
    class Meta:
        model = Nota
        fields = ["titulo", "conteudo"]


class AnamneseForm(forms.ModelForm):
    """Só os campos clínicos — servicos/insumos/plantao/total são montados
    em apps.pacientes.services.criar_anamnese, não vêm direto do ModelForm."""

    class Meta:
        model = AnamneseHist
        fields = [
            "queixa", "historico", "medicamentos", "alergias", "obs_add",
            "alimentacao", "vacina", "verme", "rua", "convive",
            "av_fc", "av_fr", "av_pa", "av_temp", "av_hidratacao", "av_mucosas",
            "av_linf_sub", "av_linf_sube", "av_linf_ing", "av_linf_pop", "av_demais",
        ]


class CirurgiaForm(forms.ModelForm):
    class Meta:
        model = CirurgiaHist
        fields = ["proc", "clinica", "anestesista", "desc_cir", "pos_op"]
