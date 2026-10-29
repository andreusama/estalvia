"""Vistas de la web local: acceso con una contraseña, curva horaria media y ficheros estáticos de lista cerrada."""
import hmac
import logging
import os
import tempfile
import time
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from estalvia.ai.gateway import ClienteAnthropic, ErrorConfig, clave_enmascarado
from estalvia.ai.masking import sellar
from estalvia.analysis.informe import construir_informe
from estalvia.analysis.nucleo import FaltaDato
from estalvia.engine.errors import EngineError
from estalvia.engine.periods import Calendario
from estalvia.engine.rules import RuleSet
from estalvia.extraction.extractor import Ajustes, CacheEnDisco, extraer_factura
from estalvia.extraction.text import ErrorTextoPdf, texto_de_pdf
from estalvia.ingestion.hourly import ingest_hourly

from .contrato import ErrorContrato, cargar_contrato
from .subida import contrato_a_yaml, contrato_desde_factura, guardar_privado, preparar_carpeta

RAIZ = Path(__file__).parents[3]

BLOQUEO_FALLOS = 5
BLOQUEO_SEGUNDOS = 60
FALLOS: list[float] = []  # instantes (monotónicos) de los intentos fallidos recientes

ESTATICOS = {"vendor/chart.umd.js": "text/javascript", "js/curva.js": "text/javascript",
             "js/subir.js": "text/javascript", "js/informe.js": "text/javascript",
             "css/web.css": "text/css"}

MAX_CSV = 2 * 1024 * 1024
MAX_PDF = 5 * 1024 * 1024
PRESUPUESTO_ANALISIS_USD = Decimal("0.50")  # tope de IA por análisis; se revisará (spec #18)
# Con 16000 el peor caso (0,33 USD) impedía el reintento dentro de 0,50 USD; la salida real ronda los 700 tokens.
AJUSTES_WEB = Ajustes(max_tokens=10000)
TOLERANCIA_LINEA_BASE = Decimal("0.005")  # 0,5 %, el umbral del TDD


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
            return redirect("/ahorro/")
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


def _subido_o(nombre: str, configurado: str) -> str:
    """El fichero subido desde la web manda sobre el que indica `.env`."""
    subido = Path(settings.UPLOADS_DIR) / nombre
    return str(subido) if subido.is_file() else configurado


def _ruta_consumo() -> str:
    return _subido_o("consumo.csv", settings.DATOS_CSV)


def _ruta_contrato() -> str:
    return _subido_o("contrato.yaml", settings.CONTRATO)


def curva(request):
    if not request.session.get("autenticado"):
        return redirect("/login/")
    contexto: dict = {}
    if not _ruta_consumo():
        contexto["aviso"] = "Sube un CSV de consumo horario arrastrándolo aquí abajo."
    else:
        try:
            ingesta = ingest_hourly(Path(_ruta_consumo()).read_bytes(), settings.DATOS_LECTOR)
            contexto["datos"] = {"horas": list(range(24)),
                                 "laborable": _media_por_hora(ingesta.lecturas, lambda d: d.weekday() < 5),
                                 "finde": _media_por_hora(ingesta.lecturas, lambda d: d.weekday() >= 5)}
        except (OSError, ValueError):
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


def _cargar_reglas():
    return RuleSet([r for f in sorted((RAIZ / "rules").glob("*.yaml")) for r in RuleSet.from_yaml(f).rules])


def _datos_graficos(informe) -> dict:
    """Solo para dibujar (los importes ya los calculó el motor): reparto del gasto y coste de energía por franja."""
    return {"perfil": {"laborable": [None if k is None else float(k) for k in informe.perfil_laborable],
                       "finde": [None if k is None else float(k) for k in informe.perfil_finde]},
            "reparto": {"nombres": [p.nombre for p in informe.reparto],
                        "importes": [float(p.importe) for p in informe.reparto]},
            "periodos": {"nombres": [f.nombre for f in informe.periodos_tarifarios],
                        "niveles": [f.nivel for f in informe.periodos_tarifarios],
                        "costes": [float(f.coste_energia) for f in informe.periodos_tarifarios]}}


def ahorro(request):
    """Informe automático: qué gasta, en qué y cómo puede pagar menos. Todo importe sale del motor."""
    if not request.session.get("autenticado"):
        return redirect("/login/")
    ctx: dict = {}
    if not _ruta_contrato():
        ctx["aviso"] = "Sube la factura en PDF (o define ESTALVIA_CONTRATO en .env) para conocer tus precios."
        return render(request, "web/ahorro.html", ctx)
    if not _ruta_consumo():
        ctx["aviso"] = "Sube un CSV de consumo horario (o define ESTALVIA_DATOS_CSV en .env)."
        return render(request, "web/ahorro.html", ctx)
    try:
        contrato = cargar_contrato(_ruta_contrato())
        ingesta = ingest_hourly(Path(_ruta_consumo()).read_bytes(), settings.DATOS_LECTOR)
    except ErrorContrato as e:
        ctx["aviso"] = f"Contrato: {e}"
        return render(request, "web/ahorro.html", ctx)
    except (OSError, ValueError):
        ctx["aviso"] = "No se pudo leer el CSV de consumo (ruta o formato)."
        return render(request, "web/ahorro.html", ctx)
    reglas, calendario = _cargar_reglas(), Calendario.desde_directorio(RAIZ / "rules/calendar")
    try:
        informe = construir_informe(contrato.site, ingesta, calendario, reglas, contrato.precios, contrato.periodo)
        total = contrato.total_factura
        if total and abs(informe.total - total) / total > TOLERANCIA_LINEA_BASE:
            ctx["aviso"] = (f"La línea base recalculada ({informe.total} €) no coincide con el total de la factura "
                            f"({total} €): no se muestra el ahorro. Revisa que el CSV cubra el periodo facturado.")
            return render(request, "web/ahorro.html", ctx)
        ctx.update(informe=informe, graficos=_datos_graficos(informe), dias=len(contrato.periodo.dias()),
                   horas=range(24))
    except (FaltaDato, EngineError) as e:
        ctx["aviso"] = f"No se puede calcular: {e}"
    except (ValueError, ArithmeticError):
        ctx["aviso"] = "No se puede calcular con los datos del contrato y del consumo; revisa el contrato."
    return render(request, "web/ahorro.html", ctx)


def _respuesta(ok: bool, mensaje: str, estado: int, **extra) -> JsonResponse:
    return JsonResponse({"ok": ok, "mensaje": mensaje, **extra}, status=estado)


def _subir_csv(datos: bytes) -> JsonResponse:
    try:
        ingesta = ingest_hourly(datos, settings.DATOS_LECTOR)
    except ValueError:  # IngestError o un fichero que no es texto UTF-8; el mensaje no repite el contenido
        return _respuesta(False, "El CSV no se puede leer: formato de consumo horario no reconocido.", 400)
    if not ingesta.lecturas:
        return _respuesta(False, "El CSV no tiene lecturas.", 400)
    guardar_privado(Path(settings.UPLOADS_DIR), "consumo.csv", datos)
    return _respuesta(True, f"CSV leído: {len(ingesta.lecturas)} horas de consumo.", 200)


def _cliente_ia():
    if settings.FABRICA_IA is not None:
        return settings.FABRICA_IA()
    return ClienteAnthropic.desde_entorno(presupuesto_usd=PRESUPUESTO_ANALISIS_USD)


def _subir_pdf(datos: bytes) -> JsonResponse:
    try:
        clave = clave_enmascarado({"ESTALVIA_MASK_KEY": settings.MASK_KEY})
        cliente = _cliente_ia()
    except ErrorConfig as e:
        return _respuesta(False, f"Falta configuración para leer la factura: {e}", 503)
    carpeta = Path(settings.UPLOADS_DIR)
    preparar_carpeta(carpeta)
    fd, temporal = tempfile.mkstemp(dir=carpeta, prefix=".", suffix=".pdf")  # 600; se borra siempre
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(datos)
        try:
            texto = sellar(texto_de_pdf(temporal), clave=clave)
        except ErrorTextoPdf as e:
            return _respuesta(False, f"No se pudo leer el PDF: {e}", 422)
        palabras = str(texto).lower()
        if "kwh" not in palabras or not ("potencia" in palabras or "potència" in palabras):
            return _respuesta(False, "El PDF no parece una factura de electricidad (no menciona kWh ni potencia): "
                                     "no se envía a la IA.", 422)
    finally:
        os.unlink(temporal)
    r = extraer_factura(texto, cliente, ajustes=AJUSTES_WEB, cache=CacheEnDisco(settings.CACHE_DIR))
    if r.en_revision:
        falla_la_ia = any(p.split(": ", 1)[-1].startswith("error de la IA") for p in r.problemas)
        mensaje = ("No se pudo consultar la IA (configuración, presupuesto o red)." if falla_la_ia
                   else "La factura necesita revisión; no se usa para calcular.")
        medidas = (f"texto enviado: {len(texto)} caracteres; tokens de entrada {r.tokens_entrada}, "
                   f"de salida {r.tokens_salida}")
        return _respuesta(False, mensaje, 422, problemas=r.problemas + [medidas])
    try:
        contrato = contrato_desde_factura(r.factura)
    except ErrorContrato as e:
        return _respuesta(False, f"La factura necesita revisión: {e}", 422, problemas=[str(e)])
    guardar_privado(carpeta, "contrato.yaml", contrato_a_yaml(contrato).encode())
    return _respuesta(True, "Factura leída: precios y potencia guardados en tu equipo.", 200)


@require_http_methods(["POST"])
def subir(request):
    """Un fichero por petición (`fichero`). El tipo se decide por la extensión y se comprueba el contenido; el
    nombre que envía el navegador no se usa nunca para escribir en disco."""
    if not request.session.get("autenticado"):
        return redirect("/login/")
    # Antes de que Django lea el cuerpo: `request.FILES` lo procesa entero, y el tamaño del fichero llega tarde.
    try:
        anunciado = int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        anunciado = 0
    if anunciado > MAX_PDF + 64 * 1024:
        return _respuesta(False, "El fichero es demasiado grande.", 413)
    f = request.FILES.get("fichero")
    if f is None:
        return _respuesta(False, "No se recibió ningún fichero.", 400)
    extension = Path(f.name).suffix.lower()
    if extension not in (".csv", ".pdf"):
        return _respuesta(False, "Solo se admiten ficheros .csv (consumo) y .pdf (factura).", 400)
    if f.size > (MAX_CSV if extension == ".csv" else MAX_PDF):
        return _respuesta(False, "El fichero es demasiado grande.", 413)
    datos = f.read()
    if extension == ".pdf":
        if not datos.startswith(b"%PDF-"):
            return _respuesta(False, "El fichero no parece un PDF.", 400)
        return _subir_pdf(datos)
    if datos.startswith(b"%PDF-"):
        return _respuesta(False, "El fichero .csv es en realidad un PDF.", 400)
    return _subir_csv(datos)


def fallo_csrf(request, reason=""):
    """403 de CSRF: el motivo (no secreto) va a la consola del servidor para poder diagnosticarlo."""
    logging.getLogger("estalvia.web").warning("CSRF rechazado en %s: %s (host=%s, origin=%s)", request.path, reason,
                                              request.get_host(), request.META.get("HTTP_ORIGIN"))
    return HttpResponseForbidden("Petición rechazada (CSRF). Recarga la página e inténtalo de nuevo.")
