"""Convite por e-mail pra definir senha — usado quando um admin de clínica
adiciona alguém que ainda não tem conta no Vettro (§5 do plano). Usa o
mecanismo de token nativo do Django (mesmo usado no "esqueci minha senha"
padrão), então nenhuma senha em texto puro passa pelo e-mail — só um link
de uso único que expira."""
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def gerar_link_definir_senha(usuario) -> str:
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)
    return f"{settings.SITE_URL}/convite/{uid}/{token}/"


def enviar_convite(usuario, clinica_nome: str) -> None:
    link = gerar_link_definir_senha(usuario)
    corpo = render_to_string("contas/email_convite.txt", {
        "usuario": usuario, "clinica_nome": clinica_nome, "link": link,
    })
    send_mail(
        subject="Você foi convidado(a) para o Vettro",
        message=corpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[usuario.email],
    )


def enviar_notificacao_novo_acesso(usuario, clinica_nome: str) -> None:
    """Pra quem JÁ tem conta e só ganhou acesso a mais uma clínica — sem
    link de senha, só um aviso."""
    corpo = render_to_string("contas/email_novo_acesso.txt", {
        "usuario": usuario, "clinica_nome": clinica_nome,
    })
    send_mail(
        subject=f"Você agora tem acesso a {clinica_nome} no Vettro",
        message=corpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[usuario.email],
    )
