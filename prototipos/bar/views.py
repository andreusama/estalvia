from django.shortcuts import render
from django.utils.translation import ngettext

from .ejemplo import GRUPOS_EJEMPLO
from .grupos import DIFF, OK, WAIT, contar, secciones


def inicio(request):
    grupos = GRUPOS_EJEMPLO
    n = contar(grupos)
    etiqueta = ngettext(
        "De %(t)d grupo: %(ok)d coinciden, %(d)d con diferencias, %(w)d pendientes",
        "De %(t)d grupos: %(ok)d coinciden, %(d)d con diferencias, %(w)d pendientes",
        len(grupos),
    ) % {"t": len(grupos), "ok": n[OK], "d": n[DIFF], "w": n[WAIT]}
    return render(
        request,
        "bar/inicio.html",
        {
            "n": n,
            "etiqueta_barra": etiqueta,
            "secciones": secciones(grupos),
            "es_ejemplo": True,
            "estados": {"ok": "=", "diff": "≠", "wait": "?"},
        },
    )
