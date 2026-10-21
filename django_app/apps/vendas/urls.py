from django.urls import path

from . import views

app_name = "vendas"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nova/", views.nova, name="nova"),
    path("cpf/", views.buscar_cpf, name="buscar_cpf"),
    path("<uuid:pk>/", views.detalhe, name="detalhe"),
    path("<uuid:pk>/pagamento/", views.pagamento, name="pagamento"),
    path("<uuid:pk>/pagamento/status/", views.pagamento_status, name="pagamento_status"),
    path("<uuid:pk>/pagamento/cobrar/", views.pagamento_cobrar, name="pagamento_cobrar"),
    path("<uuid:pk>/pagamento/cancelar/", views.pagamento_cancelar, name="pagamento_cancelar"),
    path("<uuid:pk>/pagamento/trocar/", views.pagamento_trocar, name="pagamento_trocar"),
    path("<uuid:pk>/comprovante/", views.comprovante, name="comprovante"),
    path("<uuid:pk>/cancelar/", views.cancelar, name="cancelar"),
]
