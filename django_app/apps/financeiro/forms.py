from django import forms

from .models import TipoExame, CirurgiaCategoria, Servico


from apps.core.templatetags.formatos import texto_duracao as _rotulo_duracao


# Duração na agenda: de 15 em 15 min, até 5 horas (a vet escolhe por serviço).
DURACAO_CHOICES = [(m, _rotulo_duracao(m)) for m in range(15, 301, 15)]


class ServicoForm(forms.ModelForm):
    duracao_min = forms.TypedChoiceField(label="Duração na agenda", choices=DURACAO_CHOICES, coerce=int, initial=30)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Duração antiga fora da escala de 15 min continua aparecendo pra não se perder.
        atual = getattr(self.instance, "duracao_min", None)
        if atual and atual not in dict(DURACAO_CHOICES):
            self.fields["duracao_min"].choices = sorted(DURACAO_CHOICES + [(atual, _rotulo_duracao(atual))])

    class Meta:
        model = Servico
        fields = [
            "nome", "valor", "unidade_cobranca", "duracao_min", "tipo", "na_agenda", "descricao",
            "codigo_tributacao_nacional", "codigo_servico_municipal",
        ]

    def clean_codigo_tributacao_nacional(self):
        codigo = "".join(filter(str.isdigit, self.cleaned_data.get("codigo_tributacao_nacional") or ""))
        if codigo and len(codigo) != 6:
            raise forms.ValidationError("O código de tributação nacional tem 6 dígitos (ex.: 050202).")
        return codigo


class CirurgiaCategoriaForm(forms.ModelForm):
    class Meta:
        model = CirurgiaCategoria
        fields = ["nome", "valor_p", "valor_m", "valor_g", "descricao"]

    def clean(self):
        dados = super().clean()
        if not any([dados.get("valor_p"), dados.get("valor_m"), dados.get("valor_g")]):
            raise forms.ValidationError("Informe ao menos um valor de faixa de peso (P, M ou G).")
        return dados


class TipoExameForm(forms.ModelForm):
    duracao_min = forms.TypedChoiceField(label="Duração na agenda", choices=DURACAO_CHOICES, coerce=int, initial=60)

    class Meta:
        model = TipoExame
        fields = ["nome", "duracao_min", "valor", "ativo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Valor obrigatório no cadastro (2026-10); o campo do banco segue nulo pros exames antigos.
        self.fields["valor"].required = True
        self.fields["valor"].min_value = 0


class DespesaForm(forms.ModelForm):
    class Meta:
        from .models import Despesa

        model = Despesa
        fields = ["data", "descricao", "categoria", "valor", "forma", "observacao", "comprovante"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "observacao": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_valor(self):
        valor = self.cleaned_data["valor"]
        if valor is None or valor <= 0:
            raise forms.ValidationError("O valor precisa ser maior que zero.")
        return valor
