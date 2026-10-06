from django.urls import path

from . import views

app_name = "atendimentos"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("novo/", views.novo, name="novo"),
    path("<uuid:pk>/excluir/", views.excluir, name="excluir"),
    path("vacinas/", views.vacinas, name="vacinas"),
    path("vacinas/nova/", views.vacina_salvar, name="vacina_nova"),
    path("vacinas/<uuid:pk>/editar/", views.vacina_salvar, name="vacina_editar"),
    path("vacinas/<uuid:pk>/excluir/", views.vacina_excluir, name="vacina_excluir"),
]
