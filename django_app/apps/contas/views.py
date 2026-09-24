from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_http_methods
from django_tenants.utils import schema_context

from apps.plataforma.models import LoginAudit, Usuario, UsuarioClinica

MAX_TENTATIVAS = 5
JANELA_SEGUNDOS = 15 * 60


def _chave_rate_limit(request, email: str) -> str:
    ip = request.META.get("REMOTE_ADDR", "0.0.0.0")
    return f"login_fail:{ip}:{email.strip().lower()}"


def _ip(request) -> str:
    return request.META.get("REMOTE_ADDR", "")


def _limpar_clinica_ativa(request):
    request.session.pop("clinica_schema_name", None)
    request.session.pop("clinica_id", None)
    request.session.pop("clinica_nome", None)
    request.session.pop("papel", None)


def _ativar_clinica(request, vinculo: UsuarioClinica):
    """Ativa a clínica na sessão E grava um AuditLog "login_ok" dentro do
    schema DAQUELA clínica (não só o LoginAudit global do schema public) —
    é aqui, não no login_view, que sabemos qual clínica de fato foi
    acessada. Chamado tanto num login novo quanto ao trocar de clínica."""
    request.session["clinica_schema_name"] = vinculo.clinica.schema_name
    request.session["clinica_id"] = str(vinculo.clinica_id)
    request.session["clinica_nome"] = vinculo.clinica.nome
    request.session["papel"] = vinculo.papel

    from apps.auditoria.services import registrar as registrar_auditoria

    with schema_context(vinculo.clinica.schema_name):
        registrar_auditoria(
            usuario=request.user, acao="login_ok", entidade="auth",
            detalhe="Acesso à clínica", ip=_ip(request),
        )

    destino = request.POST.get("next") or request.GET.get("next")
    return redirect(destino or "/")


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("contas:escolher_clinica")

    erro = None
    if request.method == "POST":
        email = request.POST.get("email", "")
        senha = request.POST.get("senha", "")
        chave = _chave_rate_limit(request, email)

        if cache.get(chave, 0) >= MAX_TENTATIVAS:
            erro = "Muitas tentativas de login. Tente novamente em alguns minutos."
        else:
            usuario = authenticate(request, username=email.strip().lower(), password=senha)
            if usuario is None:
                cache.set(chave, cache.get(chave, 0) + 1, timeout=JANELA_SEGUNDOS)
                erro = "E-mail ou senha inválidos."
                usuario_encontrado = Usuario.objects.filter(email=email.strip().lower()).first()
                LoginAudit.objects.create(
                    email_tentado=email.strip().lower(), usuario=usuario_encontrado,
                    sucesso=False, ip=_ip(request),
                )
            else:
                cache.delete(chave)
                LoginAudit.objects.create(
                    email_tentado=usuario.email, usuario=usuario, sucesso=True, ip=_ip(request),
                )
                login(request, usuario)
                _limpar_clinica_ativa(request)

                vinculos = list(
                    UsuarioClinica.objects.select_related("clinica").filter(usuario=usuario)
                )
                if len(vinculos) == 1:
                    return _ativar_clinica(request, vinculos[0])
                return redirect(reverse("contas:escolher_clinica") + (
                    f"?next={request.GET.get('next')}" if request.GET.get("next") else ""
                ))

    return render(request, "contas/login.html", {"erro": erro})


@login_required
@require_http_methods(["GET", "POST"])
def escolher_clinica(request):
    vinculos = list(
        UsuarioClinica.objects.select_related("clinica").filter(usuario=request.user, clinica__ativa=True)
    )

    if not vinculos:
        return render(request, "contas/sem_clinica.html")

    if len(vinculos) == 1:
        return _ativar_clinica(request, vinculos[0])

    if request.method == "POST":
        clinica_id = request.POST.get("clinica_id")
        vinculo = next((v for v in vinculos if str(v.clinica_id) == clinica_id), None)
        if vinculo:
            return _ativar_clinica(request, vinculo)

    return render(request, "contas/escolher_clinica.html", {"vinculos": vinculos})


@login_required
def logout_view(request):
    logout(request)
    return redirect("contas:login")


@require_http_methods(["GET", "POST"])
def definir_senha_view(request, uidb64, token):
    """Link de convite (§5 do plano) — mesmo mecanismo de token do "esqueci
    minha senha" nativo do Django, então nenhuma senha em texto puro passa
    pelo e-mail. Também serve pra usuário recém-criado sem senha nenhuma
    (set_unusable_password) definir a primeira senha."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        usuario = Usuario.objects.get(pk=uid)
    except (Usuario.DoesNotExist, ValueError, TypeError, OverflowError):
        usuario = None

    if usuario is None or not default_token_generator.check_token(usuario, token):
        return render(request, "contas/definir_senha_invalido.html")

    if request.method == "POST":
        form = SetPasswordForm(usuario, request.POST)
        if form.is_valid():
            form.save()
            return render(request, "contas/definir_senha_sucesso.html")
    else:
        form = SetPasswordForm(usuario)

    return render(request, "contas/definir_senha.html", {"form": form})
