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
            "criado_em": tutor.criado_em.isoformat(),
        },
        "pacientes": [
            {**p, "id": str(p["id"]), "peso": str(p["peso"]) if p["peso"] is not None else None,
             "data_nascimento": p["data_nascimento"].isoformat() if p["data_nascimento"] else None}
            for p in pacientes
        ],
    }
