"""Cabeceras de seguridad de cada respuesta: CSP estricta y nada de caché para lo que lleva datos."""
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; "
       "base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


class CabecerasDeSeguridad:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        respuesta = self.get_response(request)
        respuesta["Content-Security-Policy"] = CSP
        if not request.path.startswith("/static/"):
            respuesta["Cache-Control"] = "no-store"
        return respuesta
