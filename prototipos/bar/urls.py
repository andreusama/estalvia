from django.urls import path

from . import views

app_name = "bar"
urlpatterns = [path("", views.inicio, name="inicio")]
