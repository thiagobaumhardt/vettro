from django.urls import path

from . import views

app_name = "receitas"

urlpatterns = [
    path("<uuid:pk>/receitas/nova/", views.nova, name="nova"),
    path("<uuid:pk>/receitas/<uuid:receita_id>/", views.detalhe, name="detalhe"),
    path("<uuid:pk>/receitas/<uuid:receita_id>/pdf/", views.pdf, name="pdf"),
    path("<uuid:pk>/receitas/<uuid:receita_id>/excluir/", views.excluir, name="excluir"),
]
