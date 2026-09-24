from django.urls import path

from . import views

app_name = "tutores"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("novo/", views.form_view, name="novo"),
    path("<uuid:pk>/editar/", views.form_view, name="editar"),
    path("<uuid:pk>/", views.detalhe, name="detalhe"),
    path("<uuid:pk>/excluir/", views.excluir, name="excluir"),
    path("<uuid:pk>/exportar/", views.exportar_dados, name="exportar"),
    path("cep/", views.cep_lookup, name="cep_lookup"),
]
