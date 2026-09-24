from django.urls import path

from . import views

app_name = "usuarios_clinica"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("adicionar/", views.adicionar, name="adicionar"),
    path("<uuid:vinculo_id>/papel/", views.alterar_papel, name="alterar_papel"),
    path("<uuid:vinculo_id>/remover/", views.remover, name="remover"),
]
