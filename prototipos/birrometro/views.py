from dataclasses import replace
from decimal import Decimal
from functools import wraps

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from . import calculo
from .forms import BarrilForm
from .models import Barril, RacionBarril
from .numeros import a_decimal

MARCAS_COMUNES = [
    "Estrella Damm", "Moritz", "Estrella Galicia", "Mahou", "San Miguel", "Voll-Damm", "Heineken", "Cruzcampo",
]  # fmt: skip


def necesita_bd(vista):
    @wraps(vista)
    def envuelta(request, *a, **kw):
        if not settings.DATABASES:
            return render(request, "birrometro/sin_base_de_datos.html", {"motivo": settings.DATABASE_ERROR}, status=503)
        return vista(request, *a, **kw)

    return envuelta


def _ajax(request) -> bool:
    return request.headers.get("X-Requested-With") == "fetch"


def _inicial():
    inicial = {"fecha": timezone.localdate().isoformat(), "litros": "", "precio": "", "merma": "8", "iva_venta": "10"}
    for clave, _, cl, pvp in calculo.TIPOS:
        inicial.update({f"{clave}_cl": cl, f"{clave}_pvp": pvp, f"{clave}_n": ""})
    return inicial


def _filas_raciones(form):
    """Una fila por tipo de ración para la plantilla: tamaño, cuántas y el valor del deslizador de precio."""
    filas = []
    for clave, nombre, _, pvp in calculo.TIPOS:
        valor = form[f"{clave}_pvp"].value() or pvp
        filas.append(
            {"clave": clave, "nombre": nombre, "cl": form[f"{clave}_cl"], "n": form[f"{clave}_n"],
             "pvp": str(valor).replace(",", ".")}
        )  # fmt: skip
    return filas


def _subida(r, previo):
    anterior = previo.precio / previo.litros if previo else None
    cambio = calculo.cambio_de_precio(r.coste_litro, anterior)
    return cambio, cambio is not None and cambio >= calculo.UMBRAL_SUBIDA


def _contexto_resultado(form, barriles):
    """Resultado de los datos escritos y su comparación con el barril anterior de la marca.

    Lo que ganas por cada ración no depende de cuántas saques, así que se calcula en cuanto hay litros y precio. Si
    lo repartido se pasa de los litros, se enseña ese aviso y el total no se calcula.
    """
    if not form.is_bound:
        return {"form": form}
    form.is_valid()
    if set(form.errors) - {"__all__"}:  # algún dato suelto está mal: se explica y no se calcula nada
        return {"form": form}
    d = form.cleaned_data
    raciones = form.raciones()
    exceso = form.non_field_errors()
    if exceso:  # se calcula cada ración sin repartir nada para poder enseñar lo que ganas por ración
        raciones = [replace(r, cantidad=0) for r in raciones]
    r = calculo.calcular(d["litros"], d["precio"], raciones, d["merma"], d["iva_venta"])
    previo = calculo.anterior_de_la_marca(barriles, d["marca"], d["fecha"])
    cambio, sube = _subida(r, previo)
    return {
        "form": form, "r": r, "d": d, "previo": previo, "cambio": cambio, "sube": sube,
        "umbral": calculo.UMBRAL_SUBIDA, "exceso": exceso, "hay_total": r.sirve_algo and not exceso,
    }  # fmt: skip


def _maximo(parametros, clave):
    """El «Máx» de un tipo: cuántas caben aún, descontando lo ya repartido en los otros. Lo calcula el servidor."""
    litros, merma = a_decimal(parametros.get("litros")), a_decimal(parametros.get("merma"))
    if litros is None or not (1 <= litros <= 200):
        return {"error": "Escribe primero los litros del barril."}
    merma = Decimal("8") if merma is None else merma

    def entero(nombre, defecto=0):
        try:
            return max(int(parametros.get(nombre) or defecto), 0)
        except ValueError:
            return defecto

    cl = entero(f"{clave}_cl", 1) or 1
    otros = sum(
        (Decimal(entero(f"{k}_n") * entero(f"{k}_cl")) / 100 for k, *_ in calculo.TIPOS if k != clave), Decimal(0)
    )
    return {"n": calculo.maximo_restante(litros, merma, cl, otros)}


def _guardar(usuario, form):
    d = form.cleaned_data
    with transaction.atomic():
        barril = Barril.objects.create(
            propietario=usuario, marca=d["marca"], litros=d["litros"], fecha=d["fecha"], precio=d["precio"],
            merma=d["merma"], iva_venta=d["iva_venta"],
        )  # fmt: skip
        for orden, r in enumerate(form.raciones()):
            RacionBarril.objects.create(
                barril=barril, orden=orden, nombre=r.nombre, cl=r.cl, precio_venta=r.precio_venta, cantidad=r.cantidad
            )


@necesita_bd
def inicio(request):
    clave_maximo = request.GET.get("maximo")
    if clave_maximo in {k for k, *_ in calculo.TIPOS} and _ajax(request):
        return JsonResponse(_maximo(request.GET, clave_maximo))
    barriles = list(Barril.objects.filter(propietario=request.user).prefetch_related("raciones"))
    if request.method == "POST":
        form = BarrilForm(request.POST)
        if form.is_valid():
            _guardar(request.user, form)
            return redirect(f"{reverse('birrometro:inicio')}?hecho=guardado")
    elif "litros" in request.GET:
        form = BarrilForm(request.GET)
    else:
        form = BarrilForm(initial=_inicial())
    contexto = _contexto_resultado(form, barriles)
    if _ajax(request):  # los deslizadores piden solo el resultado; la cuenta la hace siempre el servidor
        return render(request, "birrometro/_resultado.html", contexto)
    historial = []
    for b in barriles:
        raciones = [calculo.Racion(x.nombre, x.cl, x.precio_venta, x.cantidad) for x in b.raciones.all()]
        r = calculo.calcular(b.litros, b.precio, raciones, b.merma, b.iva_venta)
        cambio, sube = _subida(r, calculo.anterior_de_la_marca(barriles, b.marca, b.fecha, excluir_pk=b.pk))
        historial.append({"b": b, "r": r, "cambio": cambio, "sube": sube})
    contexto.update(
        {
            "filas": _filas_raciones(form),
            "historial": historial,
            "marcas": sorted({b.marca for b in barriles} | set(MARCAS_COMUNES)),
            "guardado": request.GET.get("hecho") == "guardado",
        }
    )
    return render(request, "birrometro/inicio.html", contexto)
