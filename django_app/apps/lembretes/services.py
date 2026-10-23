from apps.whatsapp import modelos, services as whatsapp

from .models import EnvioLembrete, Lembrete, MensagemWhatsApp

VARIAVEL_NOME = "{nome}"


def montar_texto(texto: str, tutor) -> str:
    """Personaliza com o primeiro nome do tutor; o resto das regras da Meta
    (sem quebra de linha etc.) é aplicado no envio (modelos.limpar_parametro)."""
    primeiro_nome = (tutor.nome or "").split(" ")[0] or "tutor(a)"
    return texto.replace(VARIAVEL_NOME, primeiro_nome)


def enviar_lembrete(*, texto: str, tutores, usuario, clinica_id, clinica_nome: str, imagem=None) -> Lembrete:
    """Envia na hora, um por um (sem worker assíncrono no KingHost — mesma
    limitação do comando de lembrete automático), pelo template de aviso da
    clínica. Só manda pra quem deu consentimento de WhatsApp (LGPD) — o
    chamador já filtra, isto é defesa extra.

    Com imagem: sobe uma vez pra Meta e usa o template com cabeçalho de
    imagem pra todos (levanta ErroWhatsApp antes de enviar a qualquer um se a
    imagem não subir)."""
    imagem_id, modelo = "", modelos.AVISO
    if imagem:
        conteudo = imagem.read()
        imagem.seek(0)
        imagem_id = whatsapp.subir_imagem(clinica_id, conteudo, imagem.content_type or "image/jpeg", imagem.name)
        modelo = modelos.AVISO_IMAGEM
    lembrete = Lembrete.objects.create(
        texto=texto, usuario_id=getattr(usuario, "id", None), usuario_nome=getattr(usuario, "nome", ""), imagem=imagem,
    )
    for tutor in tutores:
        if not (tutor.consentimento_whatsapp and tutor.tel):
            continue
        mensagem = whatsapp.enviar(
            clinica_id, telefone=tutor.tel, modelo=modelo.nome, tutor=tutor, tipo=MensagemWhatsApp.Tipo.AVISO,
            parametros=modelos.parametros_aviso(tutor, clinica_nome, montar_texto(texto, tutor)), imagem_id=imagem_id,
        )
        EnvioLembrete.objects.create(
            lembrete=lembrete, tutor=tutor, tutor_nome=tutor.nome, telefone=tutor.tel,
            enviado=mensagem.enviada, mensagem=mensagem,
        )
    return lembrete
