from functools import wraps
from urllib.parse import quote

from django.conf import settings
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import ejemplo, servicios
from .comprobaciones import comprobar
from .forms import DocumentoForm, IvaFormSet, LineaFormSet, ReferenciaFormSet
from .models import Documento
from .numeros import normalizar_referencia  # noqa: F401  (se usará en la conciliación)

# Color con significado: rojo = hay que hacer algo, gris = esperando, verde = hecho
ESTILO_ESTADO = {
    Documento.Estado.PROCESADO: "diff",
    Documento.Estado.ERROR: "diff",
    Documento.Estado.PENDIENTE: "wait",
    Documento.Estado.REVISADO: "ok",
}
ORDEN_SECCIONES = [
    (Documento.Estado.PROCESADO, "Por revisar", "Léelos y confirma que están bien"),
    (Documento.Estado.ERROR, "No se pudieron leer", "Prueba otra vez o sube una foto mejor"),
    (Documento.Estado.PENDIENTE, "Por leer", "Subidos y esperando a la IA"),
    (Documento.Estado.REVISADO, "Revisados", "Ya los has comprobado"),
]


def necesita_bd(vista):
    @wraps(vista)
    def envuelta(request, *a, **kw):
        if not settings.DATABASES:
            return render(request, "bar/sin_base_de_datos.html", {"motivo": settings.DATABASE_ERROR}, status=503)
        return vista(request, *a, **kw)

    return envuelta


def _ajax(request) -> bool:
    return request.headers.get("X-Requested-With") == "fetch"


def _url_documento(d) -> str:
    """Un documento recién leído se abre en «Confirmar lectura»; los demás, en su ficha completa."""
    nombre = "bar:confirmar" if d.estado == Documento.Estado.PROCESADO else "bar:documento"
    return reverse(nombre, args=[d.pk])


@necesita_bd
def inicio(request):
    """Resumen: los documentos de verdad arriba y, debajo, los grupos de ejemplo (la conciliación aún no existe)."""
    docs = list(Documento.objects.defer("archivo", "respuesta_ia"))
    for d in docs:
        d.estilo = ESTILO_ESTADO[d.estado]
        d.url = _url_documento(d)
    hoy = timezone.localdate()
    lista = ejemplo.grupos(hoy)
    cifras = ejemplo.resumen(lista)
    return render(
        request,
        "bar/inicio.html",
        {
            "docs": docs,
            "grupos": lista,
            "cifras": cifras,
            "total_grupos": len(lista),
            "hoy": hoy,
            "confirmado": "confirmado" in request.GET,
        },
    )


@necesita_bd
def revisar(request):
    """Revisar: solo los grupos con diferencia, de mayor a menor importe (grupos de ejemplo)."""
    lista = ejemplo.con_diferencias(ejemplo.grupos(timezone.localdate()))
    cifras = ejemplo.resumen(lista)
    return render(request, "bar/revisar.html", {"grupos": lista, "cifras": cifras})


@necesita_bd
def grupo(request, slug):
    """Detalle de un grupo en página completa (sin JavaScript); con JavaScript se abre como hoja inferior."""
    for g in ejemplo.grupos(timezone.localdate()):
        if g.id == slug:
            return render(request, "bar/grupo.html", {"g": g})
    raise Http404


@necesita_bd
def confirmar(request, pk):
    """Confirmar lectura: lo que ha leído la IA, para darlo por bueno con un toque si todo es legible y cuadra.

    Si algo es dudoso o no cuadra, no se ofrece confirmar aquí: hay que revisarlo en la ficha completa.
    """
    doc = get_object_or_404(Documento.objects.defer("archivo", "respuesta_ia"), pk=pk)
    if doc.estado != Documento.Estado.PROCESADO:
        return redirect("bar:documento", pk=doc.pk)
    dudosos, _ = _dudosos(doc)
    fallos = comprobar(doc)
    limpio = not dudosos and not fallos and not doc.campos_dudosos
    if request.method == "POST":
        if not limpio:
            return redirect("bar:documento", pk=doc.pk)
        servicios.marcar_revisado(doc)
        return redirect(reverse("bar:inicio") + "?confirmado=1")
    return render(request, "bar/confirmar.html", {"doc": doc, "dudosos": dudosos, "fallos": fallos, "limpio": limpio})


@necesita_bd
def subir(request):
    if request.method != "POST":
        return render(request, "bar/subir.html", {"max_mb": servicios.MAX_BYTES // (1024 * 1024)})
    resultados = []
    for f in request.FILES.getlist("archivo"):
        try:
            doc, nuevo = servicios.crear_documento(f.name, f.content_type, f.read())
            resultados.append(
                {
                    "ok": True,
                    "id": doc.pk,
                    "nuevo": nuevo,
                    "nombre": f.name,
                    "url": reverse("bar:documento", args=[doc.pk]),
                }
            )
        except servicios.ArchivoNoValido as e:
            resultados.append({"ok": False, "nombre": f.name, "error": str(e)})
    if not resultados:
        resultados.append({"ok": False, "nombre": "", "error": "No has elegido ningún archivo."})
    if _ajax(request):
        return JsonResponse(resultados[0], status=200 if resultados[0]["ok"] else 400)
    errores = [r for r in resultados if not r["ok"]]
    if errores:
        return render(
            request, "bar/subir.html", {"errores": errores, "max_mb": servicios.MAX_BYTES // (1024 * 1024)}, status=400
        )
    return redirect(resultados[0]["url"] if len(resultados) == 1 else reverse("bar:inicio"))


@necesita_bd
@require_POST
def leer(request, pk):
    doc = get_object_or_404(Documento, pk=pk)
    servicios.leer(doc)
    destino = _url_documento(doc)
    if _ajax(request):
        return JsonResponse({"estado": doc.estado, "url": destino})
    return redirect(destino)


@necesita_bd
def archivo(request, pk):
    doc = get_object_or_404(Documento, pk=pk)
    resp = HttpResponse(bytes(doc.archivo), content_type=doc.tipo_mime)
    resp["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(doc.nombre_archivo)}"
    resp["Cache-Control"] = "private, max-age=300"
    return resp


def _dudosos(doc):
    """Lo que dudó la IA, para marcarlo junto al campo. Una vez revisado ya no se enseña."""
    if doc.estado == Documento.Estado.REVISADO:
        return {}, {}
    campos, lineas = {}, {}
    for d in doc.campos_dudosos:
        motivo = d.get("motivo") or "La IA no está segura de este dato."
        if d.get("linea"):
            lineas.setdefault(d["linea"], []).append(motivo)
        else:
            campos[d.get("campo", "otro")] = motivo
    return campos, lineas


def _registrar_cambios(doc, form, etiqueta=""):
    for nombre in form.changed_data:
        if nombre == "DELETE":
            continue
        antes, despues = form.initial.get(nombre, ""), form.cleaned_data.get(nombre, "")
        servicios.registrar(
            doc, "corregido", f"{etiqueta}{nombre}: «{antes if antes is not None else ''}» → «{despues}»"
        )


@necesita_bd
def documento(request, pk):
    doc = get_object_or_404(Documento.objects.defer("archivo", "respuesta_ia"), pk=pk)
    contexto = {"doc": doc, "estilo": ESTILO_ESTADO[doc.estado]}
    if doc.estado not in (Documento.Estado.PROCESADO, Documento.Estado.REVISADO):
        return render(request, "bar/documento_leer.html", contexto)

    if request.method == "POST":
        form = DocumentoForm(request.POST, instance=doc)
        lineas = LineaFormSet(request.POST, instance=doc, prefix="lineas")
        iva = IvaFormSet(request.POST, instance=doc, prefix="iva")
        refs = ReferenciaFormSet(request.POST, instance=doc, prefix="refs")
        if all(f.is_valid() for f in (form, lineas, iva, refs)):
            with transaction.atomic():
                _registrar_cambios(doc, form)
                form.save()
                for conjunto, nombre in ((lineas, "línea"), (iva, "IVA"), (refs, "referencia")):
                    for f in conjunto.forms:
                        if f in conjunto.deleted_forms:
                            if f.instance.pk:
                                servicios.registrar(doc, "corregido", f"{nombre} quitada")
                        elif f.has_changed():
                            _registrar_cambios(doc, f, f"{nombre} {f.instance.pk or 'nueva'}: ")
                    siguiente = (max([i.orden for i in doc.lineas.all()] or [0]) + 1) if conjunto is lineas else 0
                    for obj in conjunto.save(commit=False):
                        if conjunto is lineas and not obj.pk:
                            obj.orden, siguiente = siguiente, siguiente + 1
                        obj.save()
                    for obj in conjunto.deleted_objects:
                        obj.delete()
                doc.refresh_from_db()
                if request.POST.get("accion") == "revisar":
                    servicios.marcar_revisado(doc)
                    return redirect(reverse("bar:documento", args=[doc.pk]) + "?revisado=1")
            return redirect(reverse("bar:documento", args=[doc.pk]) + "?guardado=1")
    else:
        form = DocumentoForm(instance=doc)
        lineas = LineaFormSet(instance=doc, prefix="lineas")
        iva = IvaFormSet(instance=doc, prefix="iva")
        refs = ReferenciaFormSet(instance=doc, prefix="refs")

    dudosos, dudosos_lineas = _dudosos(doc)
    contexto.update(
        {
            "form": form,
            "lineas": lineas,
            "iva": iva,
            "refs": refs,
            "dudosos": dudosos,
            "dudosos_lineas": dudosos_lineas,
            "comprobaciones": comprobar(doc),
            "eventos": doc.eventos.all(),
            "guardado": "guardado" in request.GET,
            "revisado_ahora": "revisado" in request.GET,
            "es_pdf": doc.tipo_mime == "application/pdf",
        }
    )
    return render(request, "bar/documento.html", contexto)
