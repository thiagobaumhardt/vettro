"""§8 do plano. IMPORTANTE: o débito de estoque (SD2) de uma Cobrança já
acontece na CRIAÇÃO da Anamnese/Cirurgia que a gera (ver
apps.pacientes.services.criar_anamnese/criar_cirurgia — debitar_para_consumo
é chamado ali, não aqui). `Cobranca.insumos` é só o snapshot de preço pra
exibição/fatura. Por isso `iniciar_pagamento_tef` NÃO mexe em estoque — se
mexesse, debitaria duas vezes."""
from django.db import transaction

from .models import NotaFiscalEmitida, TransacaoTEF
from .tef import get_tef_backend


@transaction.atomic
def iniciar_pagamento_tef(cobranca, *, parcelas: int = 1, terminal_codigo: str = "", usuario=None) -> TransacaoTEF:
    """Cobra na maquininha via TEF e, se aprovado, marca a Cobrança como
    paga. Se recusado/erro, a Cobrança continua pendente e nada mais
    acontece — mesmo comportamento do botão manual "marcar como pago" da
    Fase 3, que continua existindo como fallback (§13 do plano)."""
    backend = get_tef_backend()
    resultado = backend.cobrar(valor=cobranca.total, parcelas=parcelas, terminal_codigo=terminal_codigo)

    transacao = TransacaoTEF.objects.create(
        cobranca=cobranca, valor=cobranca.total, parcelas=parcelas, status=resultado.status,
        terminal_codigo=terminal_codigo, nsu=resultado.nsu,
        codigo_autorizacao=resultado.codigo_autorizacao, bandeira=resultado.bandeira,
        mensagem_erro=resultado.mensagem_erro,
        usuario_id=getattr(usuario, "id", None), usuario_nome=getattr(usuario, "nome", ""),
    )

    if resultado.aprovado:
        from django.utils import timezone

        # Desconto via TEF ainda não suportado — cobra o total cheio (o
        # desconto hoje só existe na baixa manual, financeiro.services.registrar_pagamento).
        cobranca.status = "pago"
        cobranca.valor_pago = cobranca.total
        cobranca.pago_em = timezone.now()
        cobranca.pago_por_nome = getattr(usuario, "nome", "")
        cobranca.save(update_fields=["status", "valor_pago", "pago_em", "pago_por_nome"])

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
