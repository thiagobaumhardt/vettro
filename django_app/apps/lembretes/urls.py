from django.urls import path

from . import views

app_name = "lembretes"

urlpatterns = [
    path("", views.lista, name="lista"),
]
