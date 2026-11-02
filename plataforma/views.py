import hmac

from django.conf import settings
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .acceso import SESION


def portada(request):
    apps = [
        {
            "nombre": _("Bar"),
            "descripcion": _("Albaranes y facturas de proveedores, qué está pagado y qué no cuadra."),
            "url": reverse("bar:inicio"),
        }
    ]
    return render(request, "plataforma/portada.html", {"apps": apps})


def entrar(request):
    error = None
    destino = request.POST.get("next") or request.GET.get("next") or "/"
    if not url_has_allowed_host_and_scheme(
        destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        destino = "/"
    status = 200
    if request.method == "POST":
        if not settings.ESTALVIA_PASSWORD:
            error, status = _("El acceso no está configurado todavía."), 503
        elif hmac.compare_digest(request.POST.get("password", "").encode(), settings.ESTALVIA_PASSWORD.encode()):
            request.session.cycle_key()
            request.session[SESION] = True
            return redirect(destino)
        else:
            error, status = _("La contraseña no es correcta."), 200
    return render(request, "plataforma/entrar.html", {"error": error, "next": destino}, status=status)


@require_POST
def salir(request):
    request.session.flush()
    return redirect("/entrar/")
