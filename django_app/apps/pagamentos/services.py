"""§8 do plano. TEF de venda de balcão (cartão/Pix na maquininha integrada).
O débito de estoque NÃO acontece aqui — a Venda já baixa o estoque ao ser
criada (apps.vendas.services.registrar_venda); aqui só se fala com a
maquininha e se registra cada tentativa como TransacaoTEF."""
from django.db import transaction

from .models import NotaFiscalEmitida, TransacaoTEF
from .tef import ResultadoTEF, get_tef_backend


class TEFError(Exception):
    pass


def _aplicar(transacao: TransacaoTEF, resultado: ResultadoTEF) -> None:
    transacao.status = resultado.status
    for campo in ("id_externo", "nsu", "codigo_autorizacao", "bandeira", "adquirente", "cnpj_credenciadora", "mensagem_erro"):
        valor = getattr(resultado, campo)
        if valor:
            setattr(transacao, campo, valor[: TransacaoTEF._meta.get_field(campo).max_length])
    transacao.save()


@transaction.atomic
def iniciar_tef_venda(venda, *, usuario=None, terminal_codigo: str = "") -> TransacaoTEF:
    """Envia o total da venda pra maquininha. Uma tentativa pendente por vez."""
    if not venda.aguardando_pagamento:
        raise TEFError("Esta venda não está aguardando pagamento.")
    if venda.transacoes_tef.filter(status="pendente").exists():
        raise TEFError("Já há uma cobrança aguardando na maquininha — conclua ou cancele antes.")
    transacao = TransacaoTEF.objects.create(
        venda=venda, valor=venda.total, forma=venda.forma_pagamento, parcelas=venda.parcelas,
        status="pendente", terminal_codigo=terminal_codigo,
        usuario_id=getattr(usuario, "id", None), usuario_nome=getattr(usuario, "nome", ""),
    )
    try:
        resultado = get_tef_backend().iniciar(
            valor=venda.total, forma=venda.forma_pagamento, parcelas=venda.parcelas,
            terminal_codigo=terminal_codigo, referencia=f"venda-{venda.numero}",
        )
    except Exception as exc:  # provedor fora do ar não pode derrubar a venda
        resultado = ResultadoTEF(status="erro", mensagem_erro=f"Não foi possível falar com a maquininha: {exc}")
    _aplicar(transacao, resultado)
    return transacao


def consultar_tef(transacao: TransacaoTEF) -> TransacaoTEF:
    """Atualiza uma tentativa pendente com o que o provedor responder."""
    if transacao.status != "pendente":
        return transacao
    try:
        resultado = get_tef_backend().consultar(transacao)
    except Exception:
        return transacao  # falha momentânea de rede: continua pendente, a tela consulta de novo
    if resultado.status != "pendente":
        _aplicar(transacao, resultado)
    return transacao


def cancelar_tef(transacao: TransacaoTEF) -> TransacaoTEF:
    """Pendente → cancelado (aborta na maquininha); aprovado → estornado."""
    if transacao.status not in ("pendente", "aprovado"):
        return transacao
    era_aprovada = transacao.status == "aprovado"
    resultado = get_tef_backend().cancelar(transacao)
    if resultado.status in ("cancelado", "estornado"):
        transacao.status = "estornado" if era_aprovada else "cancelado"
        transacao.save(update_fields=["status", "atualizado_em"])
    else:
        raise TEFError(resultado.mensagem_erro or "A maquininha não confirmou o cancelamento.")
    return transacao


def registrar_nota_fiscal_pendente(cobranca, tipo: str) -> NotaFiscalEmitida:
    """Só cria o registro placeholder — NÃO chama a API da Focus NFe.
    `emitir_nfse`/`emitir_nfce` de verdade dependem de dados que ainda não
    existem no sistema (apps.configuracoes/DadosFiscaisClinica — CNPJ,
    inscrições, certificado digital A1) e de conta Focus NFe homologada;
    ver §8/§13 do plano. Levantar essa dependência explicitamente aqui em
    vez de fingir que a emissão funciona."""
    return NotaFiscalEmitida.objects.create(cobranca=cobranca, tipo=tipo, status="pendente")


def emitir_nfse(nota: NotaFiscalEmitida):
    raise NotImplementedError(
        "Emissão de NFS-e via Focus NFe depende de apps.configuracoes "
        "(dados fiscais reais da clínica) e de conta Focus NFe homologada — "
        "ainda não implementado (Fase 6, ver §8 do plano)."
    )


def emitir_nfce(nota: NotaFiscalEmitida):
    raise NotImplementedError(
        "Emissão de NFC-e via Focus NFe depende de apps.configuracoes "
        "(dados fiscais reais da clínica) e de conta Focus NFe homologada — "
        "ainda não implementado (Fase 6, ver §8 do plano)."
    )
