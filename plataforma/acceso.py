"""Contraseña única de la plataforma: toda ruta exige sesión salvo la pantalla de entrada."""

from django.shortcuts import redirect
from django.utils.http import urlencode

SESION = "estalvia_ok"
RUTAS_PUBLICAS = ("/entrar/",)


class ExigeContrasena:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in RUTAS_PUBLICAS or request.session.get(SESION):
            respuesta = self.get_response(request)
        else:
            respuesta = redirect("/entrar/?" + urlencode({"next": request.get_full_path()}))
        respuesta["X-Robots-Tag"] = "noindex, nofollow"  # herramienta privada
        return respuesta
