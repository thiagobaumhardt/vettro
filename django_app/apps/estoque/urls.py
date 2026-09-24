from django.urls import path

from . import views

app_name = "estoque"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("novo/", views.form_view, name="novo"),
    path("<uuid:pk>/editar/", views.form_view, name="editar"),
    path("<uuid:pk>/excluir/", views.excluir, name="excluir"),
    path("<uuid:pk>/ajustar/", views.ajustar, name="ajustar"),
    path("<uuid:pk>/movimentos/", views.movimentos, name="movimentos"),
    path("codigo/<str:codigo>/", views.codigo_lookup, name="codigo_lookup"),
    path("entrada-manual/", views.entrada_manual, name="entrada_manual"),
    path("importar-xml/", views.importar_xml, name="importar_xml"),
]
