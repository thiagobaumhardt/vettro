from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.configuracao, name="configuracao"),
    path("meu-perfil/", views.meu_perfil, name="meu_perfil"),
    path("perfis/<uuid:usuario_id>/", views.perfil_usuario, name="perfil_usuario"),
]
