from django.urls import path

from . import views

app_name = "pacientes"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("novo/", views.form_view, name="novo"),
    path("<uuid:pk>/editar/", views.form_view, name="editar"),
    path("<uuid:pk>/excluir/", views.excluir, name="excluir"),
    path("<uuid:pk>/", views.ficha, name="ficha"),
    path("<uuid:pk>/aba/<str:aba>/", views.ficha_aba, name="ficha_aba"),
    path("<uuid:pk>/notas/", views.nota_criar, name="nota_criar"),
    path("<uuid:pk>/notas/<uuid:nota_id>/editar/", views.nota_editar, name="nota_editar"),
    path("<uuid:pk>/notas/<uuid:nota_id>/excluir/", views.nota_excluir, name="nota_excluir"),
    path("<uuid:pk>/anamnese/", views.anamnese_criar, name="anamnese_criar"),
    path("<uuid:pk>/anamnese/<uuid:anamnese_id>/excluir/", views.anamnese_excluir, name="anamnese_excluir"),
    path("<uuid:pk>/cirurgias/", views.cirurgia_criar, name="cirurgia_criar"),
    path("<uuid:pk>/cirurgias/<uuid:cirurgia_id>/excluir/", views.cirurgia_excluir, name="cirurgia_excluir"),
    path("<uuid:pk>/exames/", views.exame_upload, name="exame_upload"),
    path("<uuid:pk>/exames/<uuid:exame_id>/excluir/", views.exame_excluir, name="exame_excluir"),
    path("<uuid:pk>/fotos/", views.foto_upload, name="foto_upload"),
    path("<uuid:pk>/fotos/<uuid:foto_id>/excluir/", views.foto_excluir, name="foto_excluir"),
    path("<uuid:pk>/cobranca/", views.cobranca_criar, name="cobranca_criar"),
    path("<uuid:pk>/cobranca/<uuid:cobranca_id>/excluir/", views.cobranca_excluir, name="cobranca_excluir"),
]
