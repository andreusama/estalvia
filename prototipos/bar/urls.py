from django.urls import path

from . import views

app_name = "bar"
urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("subir/", views.subir, name="subir"),
    path("revisar/", views.revisar, name="revisar"),
    path("pagos/", views.pagos_pantalla, name="pagos"),
    path("pagos/importar/", views.importar_extracto_vista, name="importar_extracto"),
    path("pagos/formato/", views.formato_banco, name="formato_banco"),
    path("pagos/confirmar/<int:pk>/", views.confirmar_pago_vista, name="confirmar_pago"),
    path("pagos/efectivo/<int:pk>/", views.pago_efectivo_vista, name="pago_efectivo"),
    path("pagos/ignorar/<int:pk>/", views.ignorar_movimiento, name="ignorar_movimiento"),
    path("documentos/<int:pk>/confirmar/", views.confirmar, name="confirmar"),
    path("documentos/<int:pk>/", views.documento, name="documento"),
    path("documentos/<int:pk>/archivo/", views.archivo, name="archivo"),
    path("documentos/<int:pk>/leer/", views.leer, name="leer"),
]
