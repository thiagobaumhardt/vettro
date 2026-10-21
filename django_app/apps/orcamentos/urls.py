from django.urls import path

from . import views

app_name = "orcamentos"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("novo/", views.novo, name="novo"),
    path("<uuid:pk>/", views.detalhe, name="detalhe"),
    path("<uuid:pk>/pdf/", views.pdf, name="pdf"),
    path("<uuid:pk>/excluir/", views.excluir, name="excluir"),
]
