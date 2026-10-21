from django.urls import path

from . import views_recepcao as views

app_name = "recepcao"

urlpatterns = [
    path("receber/tutor/<uuid:pk>/", views.receber_tutor, name="receber_tutor"),
    path("receber/cobranca/<uuid:pk>/", views.receber_cobranca, name="receber_cobranca"),
    path("recebimentos/<uuid:pk>/", views.recibo, name="recibo"),
]
