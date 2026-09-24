from django.urls import path

from . import views

app_name = "contas"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("clinicas/escolher/", views.escolher_clinica, name="escolher_clinica"),
    path("convite/<str:uidb64>/<str:token>/", views.definir_senha_view, name="definir_senha"),
]
