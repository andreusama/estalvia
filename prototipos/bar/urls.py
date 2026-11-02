from django.urls import path

from . import views

app_name = "bar"
urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("subir/", views.subir, name="subir"),
    path("revisar/", views.revisar, name="revisar"),
    path("grupos/<slug:slug>/", views.grupo, name="grupo"),
    path("documentos/<int:pk>/confirmar/", views.confirmar, name="confirmar"),
    path("documentos/<int:pk>/", views.documento, name="documento"),
    path("documentos/<int:pk>/archivo/", views.archivo, name="archivo"),
    path("documentos/<int:pk>/leer/", views.leer, name="leer"),
]
