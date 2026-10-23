from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.configuracao, name="configuracao"),
    path("meu-perfil/", views.meu_perfil, name="meu_perfil"),
    path("documentos/enviar/", views.documento_empresa_enviar, name="documento_empresa_enviar"),
    path("documentos/<uuid:pk>/", views.documento_empresa, name="documento_empresa"),
    path("documentos/<uuid:pk>/excluir/", views.documento_empresa_excluir, name="documento_empresa_excluir"),
    path("perfis/<uuid:usuario_id>/", views.perfil_usuario, name="perfil_usuario"),
]
