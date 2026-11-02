from django.urls import include, path

from . import views

urlpatterns = [
    path("", views.portada, name="portada"),
    path("entrar/", views.entrar, name="entrar"),
    path("salir/", views.salir, name="salir"),
    path("bar/", include("prototipos.bar.urls")),
]
