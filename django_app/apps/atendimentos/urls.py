from django.urls import path

from . import views

app_name = "atendimentos"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("novo/", views.criar, name="criar"),
    path("<uuid:pk>/excluir/", views.excluir, name="excluir"),
]
