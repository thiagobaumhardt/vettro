from django.urls import path

from . import views

app_name = "documentos"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("emitir/", views.emitir, name="emitir"),
    path("modelos/novo/", views.modelo_salvar, name="modelo_novo"),
    path("modelos/<uuid:pk>/editar/", views.modelo_salvar, name="modelo_editar"),
    path("modelos/<uuid:pk>/excluir/", views.modelo_excluir, name="modelo_excluir"),
    path("<uuid:pk>/", views.detalhe, name="detalhe"),
    path("<uuid:pk>/pdf/", views.pdf, name="pdf"),
    path("<uuid:pk>/excluir/", views.excluir, name="excluir"),
]
