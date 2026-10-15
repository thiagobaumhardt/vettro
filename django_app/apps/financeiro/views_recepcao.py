"""Telas da Recepção: receber pagamento de atendimentos finalizados."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import requer_secao
from apps.tutores.models import Tutor

from . import recepcao
from .models import Cobranca, PagamentoRecebimento, Recebimento
from .services import PagamentoInvalidoError


def _formas_do_post(post) -> list[dict]:
    return [{"forma": f, "valor": v, "parcelas": p} for f, v, p in
            zip(post.getlist("forma"), post.getlist("valor"), post.getlist("parcelas"))]


def _receber(request, *, tutor, pendentes):
    if request.method == "POST":
        selecionadas = [c for c in pendentes if str(c.pk) in request.POST.getlist("cobranca_ids")]
        try:
            rec = recepcao.receber(
                cobrancas=selecionadas, formas=_formas_do_post(request.POST),
                desconto_tipo=request.POST.get("desconto_tipo", "valor"), desconto_texto=request.POST.get("desconto", ""),
                motivo=request.POST.get("desconto_motivo", ""), cpf_nota=request.POST.get("cpf_nota", ""),
                emitir_nota=request.POST.get("emitir_nota") == "1", usuario=request.user,
            )
        except PagamentoInvalidoError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Pagamento de R$ {rec.total} recebido ({rec.formas_texto}).")
            if rec.troco:
                messages.info(request, f"Troco: R$ {rec.troco}.")
            if rec.emitir_nota:
                from apps.pagamentos.notas import emitir

                nota = emitir(recebimento=rec, clinica_nome=request.session.get("clinica_nome", ""), usuario=request.user)
                if nota.status != "emitida":
                    messages.warning(request, f"A nota de serviço não foi autorizada: {nota.mensagem_erro}")
            return redirect("recepcao:recibo", pk=rec.pk)
    return render(request, "financeiro/receber.html", {
        "tutor": tutor, "pendentes": pendentes, "formas": PagamentoRecebimento.FORMA_CHOICES,
        "cpf_inicial": tutor.cpf if tutor else "",
        "totais": {str(c.pk): float(c.total) for c in pendentes},
    })


@requer_secao("recepcao")
def receber_tutor(request, pk):
    tutor = get_object_or_404(Tutor, pk=pk)
    pendentes = list(Cobranca.objects.filter(paciente__tutor=tutor, status="pendente").select_related("paciente").order_by("criado_em"))
    if not pendentes and request.method != "POST":
        messages.info(request, f"{tutor.nome} não tem nada pendente para pagar.")
        return redirect("tutores:detalhe", pk=tutor.pk)
    return _receber(request, tutor=tutor, pendentes=pendentes)


@requer_secao("recepcao")
def receber_cobranca(request, pk):
    """Cobrança avulsa (paciente sem tutor) — recebe só ela."""
    cobranca = get_object_or_404(Cobranca.objects.select_related("paciente__tutor"), pk=pk)
    tutor = cobranca.paciente.tutor if cobranca.paciente_id else None
    if tutor:
        return redirect("recepcao:receber_tutor", pk=tutor.pk)
    if cobranca.status != "pendente":
        messages.info(request, "Esta cobrança já foi recebida.")
        return redirect("dashboard:inicio")
    return _receber(request, tutor=None, pendentes=[cobranca])


@requer_secao("recepcao")
def recibo(request, pk):
    rec = get_object_or_404(Recebimento.objects.select_related("tutor"), pk=pk)
    return render(request, "financeiro/recibo.html", {
        "rec": rec, "cobrancas": rec.cobrancas.select_related("paciente"),
        "nota": rec.notas_fiscais.order_by("-criado_em").first(),
    })
