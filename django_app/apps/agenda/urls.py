from django.urls import path

from . import views

app_name = "agenda"

urlpatterns = [
    path("", views.calendario, name="calendario"),
    path("novo/", views.novo, name="novo"),
    path("<uuid:pk>/", views.detalhe, name="detalhe"),
    path("<uuid:pk>/editar/", views.editar, name="editar"),
    path("<uuid:pk>/acao/", views.acao, name="acao"),
    path("<uuid:pk>/reagendar/", views.reagendar_view, name="reagendar"),
    path("<uuid:pk>/mover/", views.mover_view, name="mover"),
    path("<uuid:pk>/excluir/", views.excluir, name="excluir"),
    path("consultorios/", views.consultorios_lista, name="consultorios"),
    path("consultorios/novo/", views.consultorio_salvar, name="consultorio_novo"),
    path("consultorios/<uuid:pk>/editar/", views.consultorio_salvar, name="consultorio_editar"),
    path("consultorios/<uuid:pk>/excluir/", views.consultorio_excluir, name="consultorio_excluir"),
    path("bloqueios/novo/", views.bloqueio_criar, name="bloqueio_novo"),
    path("bloqueios/<uuid:pk>/excluir/", views.bloqueio_excluir, name="bloqueio_excluir"),
]
