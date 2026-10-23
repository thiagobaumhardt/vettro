"""Conectar/desconectar o WhatsApp de uma clínica e enviar mensagens.
Passo a passo de configuração na Meta: docs/whatsapp-meta.md.

Hoje (fase 1, só a Lume) a conexão usada é `conectar_manual`. O Embedded
Signup (`conectar_embedded_signup`) já está pronto e testado com a Meta
simulada, mas só entra em uso na fase 2, com o Vettro aprovado como Tech
Provider.

Fluxo de conexão (Embedded Signup — a clínica faz sozinha em ⚙️ Clínica →
WhatsApp): janela da Meta → clínica cria/escolhe a WABA e o número → volta um
`code` + waba_id + phone_number_id → `conectar_embedded_signup` troca o code
pelo token, assina os webhooks do app Vettro na WABA, registra o número na
Cloud API (exceto coexistência: o número já está no app WhatsApp Business —
aí sincroniza contatos/histórico do app, obrigatório em 24h) e cria os
templates do Vettro na WABA (aprovação da Meta leva de minutos a 1 dia).
O `code` vale só 30 segundos: a troca acontece no mesmo request.

`conectar_manual` é o mesmo sem o Embedded Signup — a plataforma informa
WABA/número/token (system user) gerados à mão no portfólio de negócios da
própria clínica. Sem coexistência: nesse caminho o número tem que ser
dedicado à API."""
import re
import secrets

from apps.lembretes.models import MensagemWhatsApp

from . import meta
from .backends import get_backend
from .meta import ErroWhatsApp
from .modelos import EXEMPLO_IMAGEM, MODELOS, limpar_parametro
from .models import ConexaoWhatsApp


def normalizar_telefone(telefone: str) -> str:
    """E.164 sem o "+" (ex: 5551999998888). Sem DDI, assume Brasil."""
    digitos = re.sub(r"\D", "", telefone or "")
    if not digitos:
        return ""
    if (telefone or "").strip().startswith("+"):
        return digitos
    if len(digitos) in (10, 11):
        return f"55{digitos}"
    return digitos


def chave_telefone(telefone: str) -> str:
    """DDD + últimos 8 dígitos — o wa_id que a Meta devolve às vezes vem sem o
    9 do celular brasileiro (55 51 9999-8888), então compara sem ele."""
    digitos = normalizar_telefone(telefone)
    if digitos.startswith("55") and len(digitos) >= 12:
        return digitos[2:4] + digitos[-8:]
    return digitos


def conexao_da_clinica(clinica_id):
    return ConexaoWhatsApp.objects.filter(clinica_id=clinica_id).first()


def pode_enviar(clinica_id) -> bool:
    """Console (dev) envia sempre; Meta só com a clínica conectada."""
    if not get_backend().requer_conexao:
        return True
    conexao = conexao_da_clinica(clinica_id)
    return bool(conexao and conexao.ativa)


# --- Conexão ----------------------------------------------------------------

def conectar_embedded_signup(clinica, *, code: str, waba_id: str, phone_number_id: str, coexistencia: bool) -> ConexaoWhatsApp:
    if not (code and waba_id and phone_number_id):
        raise ErroWhatsApp("A Meta não devolveu os dados da conta. Tente conectar de novo.")
    token = meta.trocar_code(code)
    return _ativar(clinica, waba_id, phone_number_id, token, coexistencia=coexistencia, registrar=not coexistencia)


def conectar_manual(clinica, *, waba_id: str, phone_number_id: str, token: str, registrar: bool = False) -> ConexaoWhatsApp:
    return _ativar(clinica, waba_id.strip(), phone_number_id.strip(), token.strip(), coexistencia=False, registrar=registrar)


def _ativar(clinica, waba_id, phone_number_id, token, *, coexistencia, registrar) -> ConexaoWhatsApp:
    if ConexaoWhatsApp.objects.filter(phone_number_id=phone_number_id).exclude(clinica=clinica).exists():
        raise ErroWhatsApp("Este número já está conectado a outra clínica do Vettro.")

    meta.assinar_webhooks(waba_id, token)
    pin = ""
    if registrar:
        pin = f"{secrets.randbelow(10**6):06d}"
        meta.registrar_numero(phone_number_id, token, pin)
    dados = meta.dados_numero(phone_number_id, token)

    conexao = conexao_da_clinica(clinica.pk) or ConexaoWhatsApp(clinica=clinica)
    conexao.waba_id = waba_id
    conexao.phone_number_id = phone_number_id
    conexao.numero_exibicao = dados.get("display_phone_number", "")
    conexao.nome_exibicao = dados.get("verified_name", "")
    conexao.qualidade = dados.get("quality_rating", "")
    conexao.coexistencia = coexistencia
    conexao.token = token
    if pin:
        conexao.pin = pin
    conexao.status = ConexaoWhatsApp.Status.ATIVA
    conexao.erro = ""
    conexao.save()

    if coexistencia:
        try:
            meta.sincronizar_app_business(phone_number_id, token)
        except meta.ErroMeta as exc:
            conexao.erro = f"Contatos e histórico do app não sincronizados ({exc}). Desconecte e conecte de novo em até 24h."
            conexao.save(update_fields=["erro", "atualizado_em"])
    sincronizar_modelos(conexao)
    return conexao


def sincronizar_modelos(conexao: ConexaoWhatsApp):
    """Cria na WABA os templates do Vettro que ainda não existem e atualiza o
    status de aprovação de todos. Falha num template não impede os outros."""
    existentes = {m["name"]: m for m in meta.listar_modelos(conexao.waba_id, conexao.token)}
    situacao = {}
    for modelo in MODELOS.values():
        atual = existentes.get(modelo.nome)
        if atual is None:
            try:
                handle = ""
                if modelo.cabecalho == "IMAGE":
                    handle = meta.subir_exemplo(conexao.token, EXEMPLO_IMAGEM.read_bytes(), "image/png", EXEMPLO_IMAGEM.name)
                criado = meta.criar_modelo(conexao.waba_id, conexao.token, modelo, handle)
                atual = {"status": criado.get("status", "PENDING"), "category": criado.get("category", modelo.categoria)}
            except meta.ErroMeta as exc:
                atual = {"status": "ERRO", "category": modelo.categoria, "rejected_reason": str(exc)}
        situacao[modelo.nome] = {
            "status": atual.get("status", ""),
            "categoria": atual.get("category", modelo.categoria),
            "motivo": "" if atual.get("rejected_reason") in (None, "NONE") else atual["rejected_reason"],
        }
    conexao.modelos = situacao
    conexao.save(update_fields=["modelos", "atualizado_em"])


def atualizar_dados_numero(conexao: ConexaoWhatsApp):
    dados = meta.dados_numero(conexao.phone_number_id, conexao.token)
    conexao.numero_exibicao = dados.get("display_phone_number", conexao.numero_exibicao)
    conexao.nome_exibicao = dados.get("verified_name", conexao.nome_exibicao)
    conexao.qualidade = dados.get("quality_rating", "")
    conexao.save(update_fields=["numero_exibicao", "nome_exibicao", "qualidade", "atualizado_em"])


def desconectar(conexao: ConexaoWhatsApp):
    """Para de receber os webhooks e apaga o token. O número e a WABA
    continuam da clínica na Meta — dá pra reconectar depois."""
    try:
        meta.remover_webhooks(conexao.waba_id, conexao.token)
    except meta.ErroMeta:
        pass  # token já revogado pela clínica no Meta Business: desconecta assim mesmo
    conexao.delete()


# --- Envio ------------------------------------------------------------------

def subir_imagem(clinica_id, conteudo: bytes, tipo: str, nome: str) -> str:
    """Manda a imagem de um aviso pra Meta uma vez e devolve o id (levanta
    ErroWhatsApp se não der — o aviso então não é enviado)."""
    return get_backend().subir_imagem(conexao_da_clinica(clinica_id), conteudo, tipo, nome)


def enviar(clinica_id, *, telefone: str, modelo: str, parametros, tipo: str, tutor=None, imagem_id: str = "") -> MensagemWhatsApp:
    """Envia um template e registra em MensagemWhatsApp (no schema da clínica
    ativa — o chamador já está dentro dele). Nunca levanta exceção: falha
    fica registrada com o motivo."""
    modelo_obj = MODELOS[modelo]
    parametros = [limpar_parametro(p) for p in parametros]
    numero = normalizar_telefone(telefone)
    mensagem = MensagemWhatsApp(
        tipo=tipo, tutor=tutor, telefone=telefone or "", texto=modelo_obj.renderizar(parametros), modelo=modelo,
        status=MensagemWhatsApp.Status.FALHOU,
    )

    backend = get_backend()
    conexao = conexao_da_clinica(clinica_id)
    if not numero:
        mensagem.erro = "Telefone inválido."
    elif backend.requer_conexao and not (conexao and conexao.ativa):
        mensagem.erro = "WhatsApp da clínica não está conectado."
    elif backend.requer_conexao and not conexao.modelo_aprovado(modelo):
        mensagem.erro = "Modelo de mensagem ainda não aprovado pela Meta."
    else:
        resultado = backend.enviar_modelo(conexao, numero, modelo_obj, parametros, imagem_id)
        mensagem.wamid = resultado.wamid
        mensagem.erro = resultado.erro
        if resultado.ok:
            mensagem.status = MensagemWhatsApp.Status.ENVIADA
    mensagem.save()
    return mensagem
