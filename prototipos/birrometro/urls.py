from django.urls import path

from . import views

app_name = "birrometro"
urlpatterns = [
    path("", views.inicio, name="inicio"),
]
