import json
from datetime import date, timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import requer_secao
from apps.core.models import ConfiguracaoClinica
from apps.estoque.models import Insumo
from apps.financeiro.models import CirurgiaCategoria, Servico
from apps.pacientes.models import Paciente
from apps.tutores.models import Tutor

from . import services
from .models import Orcamento


@requer_secao("orcamentos")
def lista(request):
    termo = request.GET.get("q", "").strip()
    orcamentos = Orcamento.objects.all()
    if termo:
        filtro = Q(tutor_nome__icontains=termo) | Q(pac_nome__icontains=termo)
        if termo.lstrip("#").isdigit():
            filtro |= Q(numero=int(termo.lstrip("#")))
        orcamentos = orcamentos.filter(filtro)
    pagina = Paginator(orcamentos, 50).get_page(request.GET.get("pagina"))
    return render(request, "orcamentos/lista.html", {"pagina": pagina, "termo": termo})


def _dec(valor):
    return str(valor) if valor is not None else None


def _renderizar_form(request, *, estado):
    pacientes = Paciente.objects.filter(tutor__isnull=False)
    return render(request, "orcamentos/form.html", {
        "tutores": Tutor.objects.order_by("nome"),
        "estado_json": json.dumps(estado, default=str),
        "pacientes_json": json.dumps([
            {"id": str(p.pk), "tutor": str(p.tutor_id), "nome": p.nome, "peso": _dec(p.peso)} for p in pacientes
        ]),
        # Catálogo pra adicionar itens com 1 clique (o valor continua editável).
        "catalogo_json": json.dumps({
            "servicos": [{"nome": s.nome, "valor": _dec(s.valor)} for s in Servico.objects.all()],
            "insumos": [{"nome": i.nome, "valor": _dec(i.valor)} for i in Insumo.objects.all()],
            "procedimentos": [
                {"nome": c.nome, "p": _dec(c.valor_p), "m": _dec(c.valor_m), "g": _dec(c.valor_g)}
                for c in CirurgiaCategoria.objects.all()
            ],
        }),
    })


@requer_secao("orcamentos")
def novo(request):
    if request.method != "POST":
        dias = ConfiguracaoClinica.atual().validade_orcamento_dias
        return _renderizar_form(request, estado={
            "tutor": request.GET.get("tutor", ""), "paciente": "", "valido_ate": date.today() + timedelta(days=dias),
            "obs": "", "itens": [],
        })

    post = request.POST
    estado = {
        "tutor": post.get("tutor", ""), "paciente": post.get("paciente", ""),
        "valido_ate": post.get("valido_ate", ""), "obs": post.get("obs", ""),
        "itens": [
            {"descricao": d, "qtd": q, "valor": v}
            for d, q, v in zip(post.getlist("item_descricao"), post.getlist("item_qtd"), post.getlist("item_valor"))
        ],
    }
    try:
        tutor = Tutor.objects.filter(pk=estado["tutor"]).first() if estado["tutor"] else None
        if tutor is None:
            raise services.OrcamentoInvalidoError("Selecione o tutor.")
        paciente = None
        if estado["paciente"]:
            paciente = Paciente.objects.filter(pk=estado["paciente"], tutor=tutor).first()
            if paciente is None:
                raise services.OrcamentoInvalidoError("O paciente escolhido não é deste tutor.")
        try:
            valido_ate = date.fromisoformat(estado["valido_ate"])
        except ValueError as exc:
            raise services.OrcamentoInvalidoError("Informe a data de validade.") from exc
        if valido_ate < date.today():
            raise services.OrcamentoInvalidoError("A validade não pode ser uma data passada.")
        itens = services.itens_do_post(post)
    except services.OrcamentoInvalidoError as exc:
        messages.error(request, str(exc))
        return _renderizar_form(request, estado=estado)

    orcamento = services.criar_orcamento(
        tutor=tutor, paciente=paciente, itens=itens, valido_ate=valido_ate,
        obs=estado["obs"].strip(), usuario=request.user,
    )
    messages.success(request, f"Orçamento #{orcamento.numero} criado.")
    return redirect("orcamentos:detalhe", pk=orcamento.pk)


@requer_secao("orcamentos")
def detalhe(request, pk):
    return render(request, "orcamentos/detalhe.html", {"orcamento": get_object_or_404(Orcamento, pk=pk)})


@requer_secao("orcamentos")
def pdf(request, pk):
    orcamento = get_object_or_404(Orcamento, pk=pk)
    conteudo = services.pdf_orcamento(orcamento, clinica_nome=request.session.get("clinica_nome", ""))
    resposta = HttpResponse(conteudo, content_type="application/pdf")
    # inline: abre no visualizador do navegador, de onde se imprime direto.
    resposta["Content-Disposition"] = f'inline; filename="orcamento-{orcamento.numero}.pdf"'
    return resposta


@requer_secao("orcamentos")
def excluir(request, pk):
    if request.method == "POST":
        get_object_or_404(Orcamento, pk=pk).delete()
        messages.success(request, "Orçamento excluído.")
    return redirect("orcamentos:lista")
