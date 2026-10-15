"""Regras da Agenda (estilo SimplesVet, 2026-10), organizada por consultório:
conflitos/bloqueios, grade Dia/Semana e os tempos
da ordem de chegada. As views só montam tela em cima disso."""
from datetime import date, datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone

from .models import Agendamento, BloqueioAgenda


# --- Paciente -------------------------------------------------------------------

def resolver_paciente(*, paciente, pac_nome: str, tutor_nome: str, tutor_tel: str) -> dict:
    """Porte de backend/app/routers/agendamentos.py:_resolver_paciente — quando
    um paciente cadastrado é escolhido, pac_nome/tutor_nome/tutor_tel vêm do
    cadastro (sobrescrevendo o que veio no formulário); paciente avulso usa os
    campos livres do formulário."""
    if paciente:
        return {
            "paciente": paciente,
            "pac_nome": paciente.nome,
            "tutor_nome": paciente.tutor.nome if paciente.tutor else "",
            "tutor_tel": paciente.tutor.tel if paciente.tutor else "",
        }
    return {"paciente": None, "pac_nome": pac_nome, "tutor_nome": tutor_nome, "tutor_tel": tutor_tel}


# --- Configuração da grade ------------------------------------------------------

def config_agenda() -> dict:
    from apps.core.models import ConfiguracaoClinica

    c = ConfiguracaoClinica.atual()
    inicio, fim = c.agenda_hora_inicio or time(8, 0), c.agenda_hora_fim or time(18, 0)
    if fim <= inicio:
        fim = time(23, 59)
    return {"inicio": inicio, "fim": fim, "intervalo": c.agenda_intervalo_min or 30}


def _min(t: time) -> int:
    return t.hour * 60 + t.minute


def _hora(minutos: int) -> time:
    minutos = max(0, min(minutos, 24 * 60 - 1))
    return time(minutos // 60, minutos % 60)


# --- Bloqueios e conflitos -------------------------------------------------------

def bloqueios_no_periodo(inicio: date, fim: date, *, consultorio_id=None):
    """Bloqueios que valem no período: gerais (clínica inteira) e do consultório informado."""
    alvo = Q(consultorio__isnull=True)
    if consultorio_id:
        alvo |= Q(consultorio_id=consultorio_id)
    return list(
        BloqueioAgenda.objects.filter(alvo, data_inicio__lte=fim)
        .filter(Q(data_fim__gte=inicio) | Q(data_fim__isnull=True))
        .select_related("consultorio")
    )


def bloqueio_que_cobre(data: date, hora, hora_fim=None, *, consultorio_id=None):
    for b in bloqueios_no_periodo(data, data, consultorio_id=consultorio_id):
        if b.cobre(data, hora, hora_fim):
            return b
    return None


def conflitos(data: date, hora, duracao_min: int, *, consultorio_id, excluir_id=None):
    """Agendamentos ativos do mesmo consultório que se sobrepõem ao horário."""
    if not (consultorio_id and hora):
        return []
    inicio = _min(hora)
    fim = inicio + (duracao_min or 30)
    qs = Agendamento.objects.filter(data=data, consultorio_id=consultorio_id, hora__isnull=False,
                                    status__in=Agendamento.STATUS_ATIVOS)
    if excluir_id:
        qs = qs.exclude(pk=excluir_id)
    return [a for a in qs if _min(a.hora) < fim and _min(a.hora) + (a.duracao_min or 30) > inicio]


# --- Ordem de chegada / tempos -------------------------------------------------------

class CancelamentoSemMotivoError(Exception):
    pass


def mudar_status(agendamento: Agendamento, acao: str, *, motivo: str = "", usuario=None) -> str | None:
    """Transições da agenda/fila. Devolve a mensagem de sucesso ou None se a ação não existir.
    Cancelar exige motivo (ex.: "Faltou (não compareceu)") e libera o horário."""
    agora = timezone.now()
    a = agendamento
    if acao == "chegou":
        a.status, a.chegada_em = "aguardando", a.chegada_em or agora
    elif acao == "iniciar":
        a.status = "em_atendimento"
        a.chegada_em = a.chegada_em or agora
        a.inicio_atendimento_em = a.inicio_atendimento_em or agora
    elif acao == "finalizar":
        a.status = "realizado"
        a.inicio_atendimento_em = a.inicio_atendimento_em or agora
        a.fim_atendimento_em = agora
    elif acao == "cancelar":
        motivo = (motivo or "").strip()
        if not motivo:
            raise CancelamentoSemMotivoError("Informe o motivo do cancelamento.")
        a.status, a.motivo_cancelamento = "cancelado", motivo[:200]
        a.cancelado_em, a.cancelado_por_nome = agora, getattr(usuario, "nome", "") if usuario else ""
    elif acao == "reabrir":
        a.status = "agendado"
        a.chegada_em = a.inicio_atendimento_em = a.fim_atendimento_em = None
        a.motivo_cancelamento, a.cancelado_em, a.cancelado_por_nome = "", None, ""
    else:
        return None
    a.save()
    return {
        "chegou": "Chegada registrada — paciente na fila.", "iniciar": "Atendimento iniciado.",
        "finalizar": "Atendimento finalizado.",
        "cancelar": "Agendamento cancelado — o horário ficou livre.", "reabrir": "Agendamento reaberto.",
    }[acao]


def metricas_tempos(*, desde: date, ate: date, consultorio_id=None) -> dict:
    """Médias de espera (chegada → início) e de atendimento (início → fim)."""
    qs = Agendamento.objects.filter(data__gte=desde, data__lte=ate, inicio_atendimento_em__isnull=False)
    if consultorio_id:
        qs = qs.filter(consultorio_id=consultorio_id)
    esperas = [a.espera_min for a in qs if a.espera_min is not None]
    duracoes = [a.atendimento_min for a in qs if a.atendimento_min is not None]
    media = lambda xs: round(sum(xs) / len(xs)) if xs else None  # noqa: E731
    return {"espera_media": media(esperas), "atendimento_medio": media(duracoes),
            "n_espera": len(esperas), "n_atendimento": len(duracoes)}


# --- Grade Dia/Semana ------------------------------------------------------------------

ALTURA_LINHA = 68  # px de cada intervalo na grade


def _distribuir_faixas(itens: list[dict]) -> None:
    """Põe lado a lado só os cartões que se sobrepõem: cada item recebe `faixa`
    (posição) e `faixas` (quantas dividem a largura no grupo de sobreposição
    dele). Cartão sozinho no horário ocupa a coluna inteira."""
    grupo, fim_grupo = [], None

    def fechar(grupo):
        fins = []
        for it in grupo:
            for i, f in enumerate(fins):
                if f <= it["ini"]:
                    it["faixa"], fins[i] = i, it["fim"]
                    break
            else:
                it["faixa"] = len(fins)
                fins.append(it["fim"])
        for it in grupo:
            it["faixas"] = max(1, len(fins))

    for it in sorted(itens, key=lambda x: x["ini"]):
        if grupo and it["ini"] >= fim_grupo:
            fechar(grupo)
            grupo = []
        grupo.append(it)
        fim_grupo = it["fim"] if len(grupo) == 1 else max(fim_grupo, it["fim"])
    if grupo:
        fechar(grupo)


def montar_coluna(agendamentos, bloqueios, data: date, cfg: dict) -> dict:
    """Cartões posicionados (top/altura em px) + faixas bloqueadas de uma coluna."""
    inicio, fim, passo = _min(cfg["inicio"]), _min(cfg["fim"]), cfg["intervalo"]
    escala = ALTURA_LINHA / passo
    cartoes, sem_horario = [], []
    for a in agendamentos:
        if not a.hora:
            sem_horario.append(a)
            continue
        ini = max(_min(a.hora), inicio)
        fim_a = min(_min(a.hora) + (a.duracao_min or 30), fim)
        if fim_a <= inicio or ini >= fim:
            sem_horario.append(a)  # fora da faixa da grade: aparece na lista de cima
            continue
        cartoes.append({"a": a, "ini": ini, "fim": max(fim_a, ini + passo // 2)})
    _distribuir_faixas(cartoes)
    for c in cartoes:
        faixas = c["faixas"]
        # Strings prontas pro CSS: número no template sairia localizado ("100,0") e quebraria o estilo.
        altura = max(round((c["fim"] - c["ini"]) * escala) - 2, 20)
        c["top"] = str(round((c["ini"] - inicio) * escala))
        c["altura"] = str(altura)
        c["alto"] = altura > 40
        c["largura"] = f"{100 / faixas:.3f}"
        c["esquerda"] = f"{c['faixa'] * 100 / faixas:.3f}"
    fechados = []
    for b in bloqueios:
        if not b.cobre(data):
            continue
        faixa = b.faixa
        b_ini, b_fim = (inicio, fim) if faixa is None else (max(_min(faixa[0]), inicio), min(_min(faixa[1]) + (1 if faixa[1].second else 0), fim))
        if b_fim > b_ini:
            fechados.append({"b": b, "top": str(round((b_ini - inicio) * escala)), "altura": str(round((b_fim - b_ini) * escala))})
    return {"cartoes": cartoes, "sem_horario": sem_horario, "fechados": fechados}


def posicionar_cancelados(cancelados, cfg: dict) -> list[dict]:
    """Cancelados aparecem pequenos no canto do horário (sem ocupar o espaço):
    top em px; vários no mesmo horário ficam lado a lado (`ordem`)."""
    inicio, fim, passo = _min(cfg["inicio"]), _min(cfg["fim"]), cfg["intervalo"]
    escala = ALTURA_LINHA / passo
    vistos, saida = {}, []
    for a in cancelados:
        if not a.hora or not (inicio <= _min(a.hora) < fim):
            continue
        top = round((_min(a.hora) - inicio) * escala)
        ordem = vistos.get(top, 0)
        vistos[top] = ordem + 1
        saida.append({"a": a, "top": str(top + 2 + ordem * 20), "direita": "4"})
    return saida


def linhas_da_grade(cfg: dict) -> list[time]:
    m, fim, passo, linhas = _min(cfg["inicio"]), _min(cfg["fim"]), cfg["intervalo"], []
    while m < fim:
        linhas.append(_hora(m))
        m += passo
    return linhas


def posicao_agora(data_ref: date, cfg: dict) -> int | None:
    agora = timezone.localtime()
    if agora.date() != data_ref:
        return None
    m = _min(agora.time())
    if not (_min(cfg["inicio"]) <= m <= _min(cfg["fim"])):
        return None
    return str(round((m - _min(cfg["inicio"])) * ALTURA_LINHA / cfg["intervalo"]))


def inicio_da_semana(d: date) -> date:
    """Semana começa no domingo (igual ao calendário mensal)."""
    return d - timedelta(days=(d.weekday() + 1) % 7)


def hora_atual_arredondada(cfg: dict) -> time:
    agora = timezone.localtime().time()
    passo = cfg["intervalo"]
    return _hora((_min(agora) // passo) * passo)


def combinar(data: date, hora: time) -> datetime:
    return timezone.make_aware(datetime.combine(data, hora))


class MoverInvalidoError(Exception):
    pass


def mover(agendamento: Agendamento, *, data: date, hora: time, consultorio=None, manter_consultorio=False,
          encaixe: bool = False) -> Agendamento:
    """Arrastar na grade: muda data/hora (e consultório, na visão Dia). Respeita
    bloqueios e conflitos do consultório — conflito só passa como encaixe."""
    a = agendamento
    if a.status in Agendamento.STATUS_ENCERRADOS or a.status == "em_atendimento":
        raise MoverInvalidoError("Só dá pra mover agendamento que ainda não foi atendido nem cancelado.")
    destino = a.consultorio if manter_consultorio else consultorio
    duracao = a.duracao_min or 30
    hora_fim = (datetime.combine(data, hora) + timedelta(minutes=duracao)).time()
    bloqueio = bloqueio_que_cobre(data, hora, hora_fim, consultorio_id=destino.pk if destino else None)
    if bloqueio:
        raise MoverInvalidoError(f"{bloqueio.alvo} está com a agenda fechada ({bloqueio.descricao_faixa()}): {bloqueio.motivo}.")
    em_conflito = conflitos(data, hora, duracao, consultorio_id=destino.pk if destino else None, excluir_id=a.pk)
    if em_conflito and not encaixe:
        outros = ", ".join(f"{c.hora:%H:%M} {c.pac_nome}" for c in em_conflito[:3])
        raise MoverInvalidoError(f"Horário ocupado ({outros}). Marque \"Encaixe\" para mover mesmo assim.")
    a.data, a.hora, a.consultorio = data, hora, destino
    a.encaixe = a.encaixe or bool(em_conflito)
    a.lembrete_enviado_em = None  # mudou o horário: o lembrete sai de novo
    a.save()
    return a
