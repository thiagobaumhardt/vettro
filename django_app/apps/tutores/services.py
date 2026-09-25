"""Regras de negócio de Tutor — porte de backend/app/routers/tutores.py."""
from django.utils import timezone

from .models import Tutor


def salvar_consentimento(tutor: Tutor, consentimento_anterior: bool, consentimento_novo: bool) -> None:
    """Replica a lógica de transição de consentimento LGPD do FastAPI: só
    carimba consentimento_em quando o consentimento passa de False pra True;
    limpa o timestamp se for revogado; preserva o timestamp existente se o
    valor não mudou. `consentimento_anterior` precisa vir do valor ORIGINAL
    no banco — não dá pra ler tutor.consentimento_dados aqui porque
    ModelForm.save(commit=False) já sobrescreveu o campo no instance antes
    desta função rodar."""
    if consentimento_novo and not consentimento_anterior:
        tutor.consentimento_em = timezone.now()
    elif not consentimento_novo:
        tutor.consentimento_em = None
    tutor.consentimento_dados = consentimento_novo


def salvar_consentimento_whatsapp(tutor: Tutor, consentimento_anterior: bool, consentimento_novo: bool) -> None:
    """Mesma lógica de transição de `salvar_consentimento`, só que pro
    consentimento ESPECÍFICO de lembrete via WhatsApp — mantido separado de
    propósito porque tem base legal e revogabilidade próprias (ver ressalva
    em Tutor.consentimento_whatsapp)."""
    if consentimento_novo and not consentimento_anterior:
        tutor.consentimento_whatsapp_em = timezone.now()
    elif not consentimento_novo:
        tutor.consentimento_whatsapp_em = None
    tutor.consentimento_whatsapp = consentimento_novo


PLACEHOLDER_TUTOR_EXCLUIDO = "Tutor excluído (LGPD)"


def escrubar_snapshots_tutor(tutor: Tutor) -> None:
    """Direito à eliminação (LGPD, Art. 18, IV) — excluir o Tutor por si só
    NÃO basta: Cobranca/Agendamento/Atendimento guardam snapshots
    desnormalizados de tutor_nome/tutor_tel (cópia ponto-no-tempo, não FK —
    ver §3 do plano), que sobreviveriam intactos à exclusão do Tutor. Precisa
    rodar ANTES de tutor.delete() — depois disso Paciente.tutor já virou
    null (on_delete=SET_NULL) e perdemos o vínculo pra achar os registros
    certos. Preserva o registro em si (obrigação fiscal/histórico clínico
    pode exigir retenção, LGPD Art. 16), só remove o dado pessoal do
    snapshot."""
    from apps.agenda.models import Agendamento
    from apps.atendimentos.models import Atendimento
    from apps.financeiro.models import Cobranca
    from apps.pacientes.models import Paciente

    paciente_ids = list(Paciente.objects.filter(tutor=tutor).values_list("id", flat=True))
    if not paciente_ids:
        return

    Cobranca.objects.filter(paciente_id__in=paciente_ids).update(tutor_nome=PLACEHOLDER_TUTOR_EXCLUIDO)
    for modelo in (Agendamento, Atendimento):
        modelo.objects.filter(paciente_id__in=paciente_ids).update(
            tutor_nome=PLACEHOLDER_TUTOR_EXCLUIDO, tutor_tel="",
        )


def dados_exportacao_lgpd(tutor: Tutor) -> dict:
    """Exportação de dados do titular (LGPD, art. 9/18) — tutor + pacientes
    vinculados, como no endpoint GET /tutores/{id}/exportar do FastAPI."""
    from apps.pacientes.models import Paciente

    pacientes = Paciente.objects.filter(tutor=tutor).values(
        "id", "nome", "especie", "raca", "peso", "data_nascimento", "obs"
    )
    return {
        "tutor": {
            "id": str(tutor.id),
            "nome": tutor.nome,
            "tel": tutor.tel,
            "email": tutor.email,
            "cpf": tutor.cpf,
            "endereco": tutor.endereco_completo,
            "como_conheceu": tutor.como_conheceu,
            "obs": tutor.obs,
            "consentimento_dados": tutor.consentimento_dados,
            "consentimento_em": tutor.consentimento_em.isoformat() if tutor.consentimento_em else None,
            "consentimento_whatsapp": tutor.consentimento_whatsapp,
            "consentimento_whatsapp_em": (
                tutor.consentimento_whatsapp_em.isoformat() if tutor.consentimento_whatsapp_em else None
            ),
            "criado_em": tutor.criado_em.isoformat(),
        },
        "pacientes": [
            {**p, "id": str(p["id"]), "peso": str(p["peso"]) if p["peso"] is not None else None,
             "data_nascimento": p["data_nascimento"].isoformat() if p["data_nascimento"] else None}
            for p in pacientes
        ],
    }
