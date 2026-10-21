"""⚙️ Clínica → WhatsApp (admin da clínica): conectar o número pelo Embedded
Signup da Meta, acompanhar a aprovação dos templates, testar e desconectar.

Fase 1 (hoje, só a Lume): META_EMBEDDED_SIGNUP_CONFIG_ID vazio, então a tela
não mostra os botões de conexão — a plataforma conecta à mão (admin.py) e a
clínica usa esta tela só pra acompanhar, testar e desconectar. Fase 2: com o
CONFIG_ID preenchido os botões aparecem. Ver docs/whatsapp-meta.md."""
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import admin_required
from apps.plataforma.models import Clinica

from . import services
from .meta import ErroWhatsApp
from .modelos import AVISO, MODELOS

ROTULOS_STATUS_MODELO = {
    "APPROVED": "Aprovado",
    "PENDING": "Em análise pela Meta",
    "IN_APPEAL": "Em recurso",
    "REJECTED": "Recusado",
    "PAUSED": "Pausado pela Meta",
    "DISABLED": "Desativado pela Meta",
    "ERRO": "Não foi criado",
}
ROTULOS_QUALIDADE = {"GREEN": "Alta", "YELLOW": "Média", "RED": "Baixa"}


def _clinica(request):
    return Clinica.objects.get(pk=request.session["clinica_id"])


@admin_required
def conexao(request):
    clinica = _clinica(request)
    conexao = services.conexao_da_clinica(clinica.pk)
    modelos = []
    for modelo in MODELOS.values():
        situacao = (conexao.modelos.get(modelo.nome) if conexao else None) or {}
        modelos.append({
            "rotulo": modelo.rotulo,
            "categoria": "Marketing" if situacao.get("categoria", modelo.categoria) == "MARKETING" else "Utilidade",
            "status": situacao.get("status", ""),
            "status_rotulo": ROTULOS_STATUS_MODELO.get(situacao.get("status"), situacao.get("status") or "—"),
            "motivo": situacao.get("motivo", ""),
        })
    return render(request, "whatsapp/conexao.html", {
        "conexao": conexao,
        "modelos": modelos,
        "qualidade": ROTULOS_QUALIDADE.get(conexao.qualidade, "") if conexao else "",
        "modulo_ativo": clinica.modulo_whatsapp_lembrete,
        "signup_disponivel": bool(settings.META_APP_ID and settings.META_EMBEDDED_SIGNUP_CONFIG_ID),
        "meta_app_id": settings.META_APP_ID,
        "meta_config_id": settings.META_EMBEDDED_SIGNUP_CONFIG_ID,
        "meta_versao": settings.META_GRAPH_VERSION,
    })


@admin_required
@require_POST
def conectar(request):
    try:
        services.conectar_embedded_signup(
            _clinica(request),
            code=request.POST.get("code", ""),
            waba_id=request.POST.get("waba_id", ""),
            phone_number_id=request.POST.get("phone_number_id", ""),
            coexistencia=request.POST.get("coexistencia") == "1",
        )
    except ErroWhatsApp as exc:
        messages.error(request, f"Não foi possível conectar o WhatsApp: {exc}")
    else:
        messages.success(request, "WhatsApp conectado. Os modelos de mensagem foram enviados para aprovação da Meta.")
    return redirect("whatsapp:conexao")


@admin_required
@require_POST
def sincronizar(request):
    conexao = services.conexao_da_clinica(request.session["clinica_id"])
    if conexao:
        try:
            services.atualizar_dados_numero(conexao)
            services.sincronizar_modelos(conexao)
        except ErroWhatsApp as exc:
            messages.error(request, f"Não foi possível atualizar: {exc}")
        else:
            messages.success(request, "Situação atualizada.")
    return redirect("whatsapp:conexao")


@admin_required
@require_POST
def testar(request):
    telefone = request.POST.get("telefone", "").strip()
    mensagem = services.enviar(
        request.session["clinica_id"], telefone=telefone, modelo=AVISO.nome, tipo="teste",
        parametros=[request.user.nome, request.session.get("clinica_nome", ""), "Teste do Vettro: o WhatsApp da clínica está conectado."],
    )
    if mensagem.enviada:
        messages.success(request, f"Mensagem de teste enviada para {telefone}.")
    else:
        messages.error(request, f"Teste não enviado: {mensagem.erro}")
    return redirect("whatsapp:conexao")


@admin_required
@require_POST
def desconectar(request):
    conexao = services.conexao_da_clinica(request.session["clinica_id"])
    if conexao:
        services.desconectar(conexao)
        messages.success(request, "WhatsApp desconectado. Os lembretes param de ser enviados.")
    return redirect("whatsapp:conexao")
