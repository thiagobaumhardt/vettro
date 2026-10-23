"""Recepção: atendimentos finalizados aguardando pagamento e o recebimento
(várias cobranças do tutor de uma vez, dividido em até 4 formas de pagamento).
O vet finaliza o atendimento (Anamnese/Cirurgia/Atendimento) → nasce a
Cobrança pendente → a recepção recebe aqui."""
import re
from decimal import Decimal, InvalidOperation

from django.db import connection, transaction
from django.db.models import Max
from django.utils import timezone

from apps.core.validators import cpf_valido

from .models import Cobranca, PagamentoRecebimento, Recebimento
from .services import PagamentoInvalidoError, calcular_desconto

MAX_FORMAS = 4


def pendentes_por_tutor() -> list[dict]:
    """Cobranças pendentes agrupadas por tutor (ou por paciente sem tutor),
    mais antigas primeiro — a fila da recepção."""
    grupos = {}
    for c in Cobranca.objects.filter(status="pendente").select_related("paciente__tutor").order_by("criado_em"):
        tutor = c.paciente.tutor if c.paciente_id else None
        chave = f"t{tutor.pk}" if tutor else f"c{c.pk}"
        g = grupos.setdefault(chave, {"tutor": tutor, "nome": tutor.nome if tutor else (c.tutor_nome or "Sem tutor"),
                                      "cobrancas": [], "total": Decimal("0"), "pacientes": [], "pacientes_obj": [], "desde": c.criado_em,
                                      "cobranca_unica": None if tutor else c})
        g["cobrancas"].append(c)
        g["total"] += c.total
        if c.paciente_id and c.paciente.nome not in g["pacientes"]:
            g["pacientes"].append(c.paciente.nome)
            g["pacientes_obj"].append(c.paciente)  # pros links da fila (Ficha do paciente)
    return list(grupos.values())


def _dec(texto) -> Decimal:
    """Aceita "1.234,56", "50,5" ou "50.00"."""
    texto = str(texto or "").strip() or "0"
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return Decimal(texto)
    except InvalidOperation as exc:
        raise PagamentoInvalidoError(f"Valor inválido: {texto}") from exc


def formatar_cpf(cpf: str) -> str:
    d = re.sub(r"\D", "", cpf or "")
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}" if len(d) == 11 else (cpf or "")


def _proximo_numero() -> int:
    with connection.cursor() as cursor:
        cursor.execute(f"LOCK TABLE {Recebimento._meta.db_table} IN SHARE ROW EXCLUSIVE MODE")
    return (Recebimento.objects.aggregate(m=Max("numero"))["m"] or 0) + 1


def _ratear(valor: Decimal, cobrancas: list, subtotal: Decimal) -> list[Decimal]:
    """Divide o desconto entre as cobranças proporcionalmente ao total de
    cada uma (centavos que sobram vão na última)."""
    if not valor or not subtotal:
        return [Decimal("0")] * len(cobrancas)
    partes = [(valor * c.total / subtotal).quantize(Decimal("0.01")) for c in cobrancas]
    partes[-1] += valor - sum(partes)
    return partes


@transaction.atomic
def receber(*, cobrancas: list, formas: list[dict], desconto_tipo: str, desconto_texto: str, motivo: str,
            cpf_nota: str, emitir_nota: bool, usuario) -> Recebimento:
    """`formas` = [{"forma": "pix", "valor": "50,00", "parcelas": 1}, ...].
    A soma tem que fechar o total (com desconto); só dinheiro pode passar —
    o excedente vira troco."""
    cobrancas = list(Cobranca.objects.select_for_update(of=("self",)).filter(pk__in=[c.pk for c in cobrancas]).select_related("paciente__tutor"))
    if not cobrancas:
        raise PagamentoInvalidoError("Selecione ao menos uma cobrança para receber.")
    if any(c.status != "pendente" for c in cobrancas):
        raise PagamentoInvalidoError("Alguma das cobranças já foi recebida — atualize a tela.")
    tutores = {c.paciente.tutor_id for c in cobrancas if c.paciente_id}
    if len(tutores) > 1:
        raise PagamentoInvalidoError("Receba cobranças de um tutor por vez.")

    subtotal = sum((c.total for c in cobrancas), Decimal("0"))
    informado = _dec(desconto_texto) if (desconto_texto or "").strip() else Decimal("0")
    desconto = calcular_desconto(subtotal, desconto_tipo or "valor", informado) if informado else Decimal("0")
    motivo = (motivo or "").strip()
    if desconto > 0 and not motivo:
        raise PagamentoInvalidoError("Informe o motivo do desconto.")
    total = subtotal - desconto

    linhas = []
    for f in formas:
        valor = _dec(f.get("valor"))
        if valor <= 0:
            continue
        if f.get("forma") not in dict(PagamentoRecebimento.FORMA_CHOICES):
            raise PagamentoInvalidoError("Escolha a forma de pagamento de cada valor.")
        parcelas = int(f.get("parcelas") or 1) if f.get("forma") == "credito" else 1
        linhas.append({"forma": f["forma"], "valor": valor.quantize(Decimal("0.01")), "parcelas": max(1, min(parcelas, 12))})
    if not linhas:
        raise PagamentoInvalidoError("Informe a forma de pagamento e o valor recebido.")
    if len(linhas) > MAX_FORMAS:
        raise PagamentoInvalidoError(f"No máximo {MAX_FORMAS} formas de pagamento por recebimento.")

    pago = sum((l["valor"] for l in linhas), Decimal("0"))
    em_dinheiro = sum((l["valor"] for l in linhas if l["forma"] == "dinheiro"), Decimal("0"))
    if pago < total:
        raise PagamentoInvalidoError(f"Faltam R$ {total - pago:.2f} para fechar o total de R$ {total:.2f}.".replace(".", ","))
    troco = pago - total
    if troco > em_dinheiro:
        raise PagamentoInvalidoError("O valor passa do total — só pagamento em dinheiro pode ter troco.")
    # O troco sai do dinheiro: guarda o valor efetivamente abatido em cada forma.
    resto_troco = troco
    for l in linhas:
        if l["forma"] == "dinheiro" and resto_troco > 0:
            abate = min(resto_troco, l["valor"])
            l["valor"] -= abate
            resto_troco -= abate
    linhas = [l for l in linhas if l["valor"] > 0]

    cpf_nota = (cpf_nota or "").strip()
    if cpf_nota:
        if not cpf_valido(cpf_nota):
            raise PagamentoInvalidoError("CPF na nota inválido — confira os números ou deixe em branco.")
        cpf_nota = formatar_cpf(cpf_nota)

    tutor = cobrancas[0].paciente.tutor if cobrancas[0].paciente_id else None
    rec = Recebimento.objects.create(
        numero=_proximo_numero(), tutor=tutor, tutor_nome=tutor.nome if tutor else cobrancas[0].tutor_nome,
        cpf_nota=cpf_nota, emitir_nota=emitir_nota, subtotal=subtotal,
        desconto_tipo=(desconto_tipo or "valor") if desconto > 0 else "",
        desconto_informado=informado if desconto > 0 else None, desconto_valor=desconto,
        desconto_motivo=motivo if desconto > 0 else "", total=total, troco=troco,
        usuario_nome=getattr(usuario, "nome", ""),
    )
    for l in linhas:
        PagamentoRecebimento.objects.create(recebimento=rec, **l)

    agora = timezone.now()
    for c, parte in zip(cobrancas, _ratear(desconto, cobrancas, subtotal)):
        c.recebimento = rec
        c.status, c.pago_em, c.pago_por_nome = "pago", agora, getattr(usuario, "nome", "")
        c.desconto_tipo = "valor" if parte > 0 else ""
        c.desconto_informado = parte if parte > 0 else None
        c.desconto_valor, c.desconto_motivo = parte, motivo if parte > 0 else ""
        c.valor_pago = c.total - parte
        c.save()
    return rec
