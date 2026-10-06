from django.urls import path

from . import views

app_name = "vendas"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nova/", views.nova, name="nova"),
    path("<uuid:pk>/", views.detalhe, name="detalhe"),
    path("<uuid:pk>/comprovante/", views.comprovante, name="comprovante"),
    path("<uuid:pk>/cancelar/", views.cancelar, name="cancelar"),
]
