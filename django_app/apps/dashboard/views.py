from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def inicio(request):
    """Placeholder da Fase 1 — só prova que o schema da clínica ativa está
    correto e o shell (sidebar/topbar/tailwind/htmx/alpine) renderiza. As
    estatísticas reais (Tutores/Pacientes/Estoque/Agenda) chegam nas Fases
    2-4 conforme os módulos correspondentes forem implementados."""
    return render(request, "dashboard/inicio.html")
