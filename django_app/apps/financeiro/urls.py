from django.urls import path

from . import views

app_name = "financeiro"

urlpatterns = [
    path("", views.catalogo, name="catalogo"),
    path("servicos/novo/", views.servico_salvar, name="servico_novo"),
    path("servicos/<uuid:pk>/editar/", views.servico_salvar, name="servico_editar"),
    path("servicos/<uuid:pk>/excluir/", views.servico_excluir, name="servico_excluir"),
    path("categorias/novo/", views.categoria_salvar, name="categoria_novo"),
    path("categorias/<uuid:pk>/editar/", views.categoria_salvar, name="categoria_editar"),
    path("categorias/<uuid:pk>/excluir/", views.categoria_excluir, name="categoria_excluir"),
    path("cobrancas/<uuid:pk>/pagar/", views.cobranca_pagar, name="cobranca_pagar"),
]
