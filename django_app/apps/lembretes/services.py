import re

from apps.agenda.notificacoes import get_backend

from .models import EnvioLembrete, Lembrete

VARIAVEL_NOME = "{nome}"


def montar_texto(texto: str, tutor) -> str:
    """Personaliza com o primeiro nome do tutor e ajusta pro limite da Meta:
    variável de template não aceita quebra de linha/tab nem mais de 4 espaços
    seguidos (ver WhatsAppMetaCloudBackend)."""
    primeiro_nome = (tutor.nome or "").split(" ")[0] or "tutor(a)"
    texto = texto.replace(VARIAVEL_NOME, primeiro_nome)
    texto = re.sub(r"[\r\n\t]+", " ", texto)
    return re.sub(r" {4,}", "   ", texto).strip()


def enviar_lembrete(*, texto: str, tutores, usuario) -> Lembrete:
    """Envia na hora, um por um (sem worker assíncrono no KingHost — mesma
    limitação do comando de lembrete automático). Só manda pra quem deu
    consentimento de WhatsApp (LGPD) — o chamador já filtra, isto é defesa extra."""
    backend = get_backend()
    lembrete = Lembrete.objects.create(
        texto=texto, usuario_id=getattr(usuario, "id", None), usuario_nome=getattr(usuario, "nome", ""),
    )
    for tutor in tutores:
        if not (tutor.consentimento_whatsapp and tutor.tel):
            continue
        enviado = backend.enviar(tutor.tel, montar_texto(texto, tutor))
        EnvioLembrete.objects.create(
            lembrete=lembrete, tutor=tutor, tutor_nome=tutor.nome, telefone=tutor.tel, enviado=enviado,
        )
    return lembrete
