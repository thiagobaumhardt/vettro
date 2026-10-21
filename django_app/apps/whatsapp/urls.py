from django.urls import path

from . import views

app_name = "whatsapp"

urlpatterns = [
    path("", views.conexao, name="conexao"),
    path("conectar/", views.conectar, name="conectar"),
    path("sincronizar/", views.sincronizar, name="sincronizar"),
    path("testar/", views.testar, name="testar"),
    path("desconectar/", views.desconectar, name="desconectar"),
]
