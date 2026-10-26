from django.urls import path

from . import views

urlpatterns = [
    path("", views.curva, name="curva"),
    path("login/", views.entrar, name="login"),
    path("static/<path:nombre>", views.estatico, name="static"),
]
