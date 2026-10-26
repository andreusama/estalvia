from django.urls import path

from . import views

urlpatterns = [
    path("", views.curva, name="curva"),
    path("ahorro/", views.ahorro, name="ahorro"),
    path("logout/", views.salir, name="logout"),
    path("login/", views.entrar, name="login"),
    path("static/<path:nombre>", views.estatico, name="static"),
]
