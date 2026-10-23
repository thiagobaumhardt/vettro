from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.shortcuts import redirect, render

from apps.core.decorators import requer_secao
from apps.tutores.models import Tutor
from apps.whatsapp import services as whatsapp
from apps.whatsapp.meta import ErroWhatsApp

from . import services
from .models import Lembrete, MensagemWhatsApp

LIMITE_TEXTO = 900  # folga pro texto fixo do template da Meta (limite do corpo: 1024)


@requer_secao("lembretes")
def lista(request):
    if request.method == "POST":
        return _enviar(request)
    return _renderizar(request)


def _renderizar(request, texto="", selecionados=()):
    # Busca é filtrada no navegador (Alpine) pra não perder a seleção feita.
    tutores = Tutor.objects.order_by("nome")
    historico = Lembrete.objects.annotate(
        total=Count("envios"), enviados=Count("envios", filter=Q(envios__enviado=True)),
        lidos=Count("envios", filter=Q(envios__mensagem__status=MensagemWhatsApp.Status.LIDA)),
    )[:20]
    return render(request, "lembretes/lista.html", {
        "tutores": tutores, "texto": texto, "selecionados": set(selecionados),
        "historico": historico,
        "limite_texto": LIMITE_TEXTO, "variavel_nome": services.VARIAVEL_NOME,
        "conectado": whatsapp.pode_enviar(request.session.get("clinica_id")),
    })


def _enviar(request):
    texto = request.POST.get("texto", "").strip()
    ids = request.POST.getlist("tutor_ids")
    if not texto:
        messages.error(request, "Escreva o texto do lembrete.")
        return _renderizar(request, texto, ids)
    if len(texto) > LIMITE_TEXTO:
        messages.error(request, f"O texto passou do limite de {LIMITE_TEXTO} caracteres.")
        return _renderizar(request, texto, ids)
    # LGPD: só tutores com consentimento específico de WhatsApp.
    tutores = list(Tutor.objects.filter(pk__in=ids, consentimento_whatsapp=True).exclude(tel=""))
    if not tutores:
        messages.error(request, "Selecione ao menos um tutor com consentimento de WhatsApp.")
        return _renderizar(request, texto, ids)

    if not whatsapp.pode_enviar(request.session.get("clinica_id")):
        messages.error(request, "O WhatsApp da clínica não está conectado.")
        return _renderizar(request, texto, ids)

    imagem = request.FILES.get("imagem")
    if imagem:
        try:
            for validador in Lembrete._meta.get_field("imagem").validators:
                validador(imagem)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return _renderizar(request, texto, ids)

    try:
        lembrete = services.enviar_lembrete(
            texto=texto, tutores=tutores, usuario=request.user, imagem=imagem,
            clinica_id=request.session.get("clinica_id"), clinica_nome=request.session.get("clinica_nome", ""),
        )
    except ErroWhatsApp as exc:
        messages.error(request, f"Não foi possível enviar a imagem para o WhatsApp: {exc}")
        return _renderizar(request, texto, ids)
    enviados = lembrete.envios.filter(enviado=True).count()
    falhas = lembrete.envios.count() - enviados
    if falhas:
        messages.warning(request, f"{enviados} lembrete(s) enviado(s), {falhas} falharam — veja o histórico.")
    else:
        messages.success(request, f"{enviados} lembrete(s) enviado(s).")
    return redirect("lembretes:lista")
