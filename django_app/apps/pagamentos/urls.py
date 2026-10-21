from django.urls import path

from . import views

app_name = "notas"

urlpatterns = [
    path("contabilidade/", views.contabilidade, name="contabilidade"),
    path("contabilidade/pacote.zip", views.contabilidade_zip, name="contabilidade_zip"),
    path("<uuid:pk>/pdf/", views.pdf, name="pdf"),
    path("cobranca/<uuid:pk>/emitir/", views.emitir_cobranca, name="emitir_cobranca"),
    path("venda/<uuid:pk>/emitir/", views.emitir_venda, name="emitir_venda"),
    path("recebimento/<uuid:pk>/emitir/", views.emitir_recebimento, name="emitir_recebimento"),
]
