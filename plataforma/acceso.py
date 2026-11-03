"""Acceso por cuenta de usuario: toda ruta exige sesión salvo la entrada y el registro."""

from django.shortcuts import redirect
from django.utils.http import urlencode

RUTAS_PUBLICAS = ("/entrar/", "/registro/")


class ExigeUsuario:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in RUTAS_PUBLICAS or request.user.is_authenticated:
            respuesta = self.get_response(request)
        else:
            respuesta = redirect("/entrar/?" + urlencode({"next": request.get_full_path()}))
        respuesta["X-Robots-Tag"] = "noindex, nofollow"  # herramienta privada
        return respuesta
