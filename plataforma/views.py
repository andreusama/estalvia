import hmac

from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .forms import RegistroForm


def portada(request):
    apps = [
        {
            "nombre": _("Bar"),
            "descripcion": _("Albaranes y facturas de proveedores, qué está pagado y qué no cuadra."),
            "url": reverse("bar:inicio"),
        }
    ]
    return render(request, "plataforma/portada.html", {"apps": apps})


def _destino(request) -> str:
    destino = request.POST.get("next") or request.GET.get("next") or "/"
    ok = url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}, require_https=request.is_secure())
    return destino if ok else "/"


def entrar(request):
    destino = _destino(request)
    if request.user.is_authenticated:
        return redirect(destino)
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect(destino)
    contexto = {"form": form, "next": destino, "registro_abierto": bool(settings.ESTALVIA_CODIGO_INVITACION)}
    return render(request, "plataforma/entrar.html", contexto)


def registro(request):
    """Crear una cuenta con el código de invitación. Sin código configurado, el registro está cerrado."""
    if not settings.ESTALVIA_CODIGO_INVITACION:
        return render(request, "plataforma/registro_cerrado.html", status=403)
    destino = _destino(request)
    form = RegistroForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        codigo = form.cleaned_data["codigo"].encode()
        if hmac.compare_digest(codigo, settings.ESTALVIA_CODIGO_INVITACION.encode()):
            login(request, form.save())
            return redirect(destino)
        form.add_error("codigo", _("El código de invitación no es correcto."))
    return render(request, "plataforma/registro.html", {"form": form, "next": destino})


@require_POST
def salir(request):
    logout(request)
    return redirect("/entrar/")
