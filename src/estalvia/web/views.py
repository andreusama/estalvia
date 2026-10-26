"""Vistas de la web local: acceso con una contraseña, curva horaria media y ficheros estáticos de lista cerrada."""
import hmac
import time
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from estalvia.ingestion.hourly import IngestError, ingest_hourly

BLOQUEO_FALLOS = 5
BLOQUEO_SEGUNDOS = 60
FALLOS: list[float] = []  # instantes (monotónicos) de los intentos fallidos recientes

ESTATICOS = {"vendor/chart.umd.js": "text/javascript", "js/curva.js": "text/javascript",
             "css/web.css": "text/css"}


def _bloqueado() -> bool:
    ahora = time.monotonic()
    FALLOS[:] = [t for t in FALLOS if ahora - t < BLOQUEO_SEGUNDOS]
    return len(FALLOS) >= BLOQUEO_FALLOS


@require_http_methods(["GET", "POST"])
def entrar(request):
    if request.method == "POST":
        if _bloqueado():
            return render(request, "web/login.html", {"error": "Demasiados intentos; espera un minuto."}, status=429)
        enviada = request.POST.get("password", "").encode()
        if hmac.compare_digest(enviada, settings.WEB_PASSWORD.encode()):
            request.session.flush()
            request.session["autenticado"] = True
            return redirect("/")
        FALLOS.append(time.monotonic())
        return render(request, "web/login.html", {"error": "Contraseña incorrecta."})
    return render(request, "web/login.html", {})


@require_http_methods(["POST"])
def salir(request):
    request.session.flush()
    return redirect("/login/")


def _media_por_hora(lecturas, filtro) -> list[float | None]:
    """kWh medios por hora local del día. Solo para dibujar: no es un importe."""
    sumas, cuentas = defaultdict(Decimal), defaultdict(int)
    for x in lecturas:
        if filtro(x.instante_local.date()):
            sumas[x.instante_local.hour] += x.kwh
            cuentas[x.instante_local.hour] += 1
    return [float(sumas[h] / cuentas[h]) if cuentas[h] else None for h in range(24)]


def curva(request):
    if not request.session.get("autenticado"):
        return redirect("/login/")
    contexto: dict = {}
    if not settings.DATOS_CSV:
        contexto["aviso"] = "Falta ESTALVIA_DATOS_CSV en .env: la ruta de un CSV de consumo horario."
    else:
        try:
            ingesta = ingest_hourly(Path(settings.DATOS_CSV).read_bytes(), settings.DATOS_LECTOR)
            contexto["datos"] = {"horas": list(range(24)),
                                 "laborable": _media_por_hora(ingesta.lecturas, lambda d: d.weekday() < 5),
                                 "finde": _media_por_hora(ingesta.lecturas, lambda d: d.weekday() >= 5)}
        except (OSError, IngestError):
            contexto["aviso"] = "No se pudo leer el CSV de consumo (ruta o formato)."
    return render(request, "web/curva.html", contexto)


def estatico(request, nombre):
    tipo = ESTATICOS.get(nombre)
    if tipo is None:
        raise Http404
    ruta = Path(__file__).parent / "static" / nombre
    if not ruta.is_file():
        raise Http404
    return FileResponse(ruta.open("rb"), content_type=tipo)
