from django import forms

from apps.plataforma.models import Usuario, UsuarioClinica


class AdicionarUsuarioForm(forms.Form):
    """Admin da clínica adiciona alguém pelo e-mail. Se o e-mail já existe
    como Usuario global (ex: vet que já atende em outra clínica), só cria o
    vínculo (UsuarioClinica) — reaproveita a identidade, não duplica (§5 do
    plano). Se não existe, cria o Usuario global SEM senha
    (set_unusable_password) e manda um convite por e-mail pra pessoa
    definir a própria senha — o admin nunca fica sabendo a senha de
    ninguém."""

    email = forms.EmailField()
    nome = forms.CharField(max_length=150, required=False, help_text="Só necessário se essa pessoa ainda não tem conta no Vettro.")
    papel = forms.ChoiceField(choices=UsuarioClinica.PAPEL_CHOICES)

    def clean(self):
        dados = super().clean()
        email = (dados.get("email") or "").strip().lower()
        dados["email"] = email
        dados["usuario_existente"] = Usuario.objects.filter(email=email).exists()

        if not dados["usuario_existente"] and not dados.get("nome"):
            self.add_error("nome", "Informe o nome — esse e-mail ainda não tem conta no Vettro.")
        return dados


class PapelForm(forms.Form):
    papel = forms.ChoiceField(choices=UsuarioClinica.PAPEL_CHOICES)
