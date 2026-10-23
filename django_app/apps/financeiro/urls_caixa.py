from django.urls import path

from . import views_caixa as views

app_name = "caixa"

urlpatterns = [
    path("", views.painel, name="painel"),
    path("saidas/nova/", views.despesa_salvar, name="despesa_nova"),
    path("saidas/<uuid:pk>/editar/", views.despesa_salvar, name="despesa_editar"),
    path("saidas/<uuid:pk>/excluir/", views.despesa_excluir, name="despesa_excluir"),
    path("saidas/<uuid:pk>/comprovante/", views.comprovante, name="comprovante"),
    path("reposicao/alternar/", views.reposicao_alternar, name="reposicao_alternar"),
]
