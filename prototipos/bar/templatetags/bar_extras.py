from django import template
from django.utils import timezone

from .. import ejemplo
from ..numeros import eur as _eur

register = template.Library()


@register.filter
def eur(valor):
    return _eur(valor)


@register.filter
def get_item(diccionario, clave):
    """dudosos_lineas|get_item:3 → lista de motivos de la línea 3 (vacía si no hay)."""
    return diccionario.get(clave, [])


@register.filter
def centimos(valor):
    """Importe en céntimos enteros, para que el JavaScript sume sin decimales."""
    return int(valor * 100)


@register.inclusion_tag("bar/_tabbar.html", takes_context=True)
def tabbar(context):
    """Barra inferior: Resumen · Subir · Revisar (el contador rojo solo si hay diferencias sin resolver)."""
    request = context["request"]
    nombre = request.resolver_match.url_name if request.resolver_match else ""
    activa = nombre if nombre in ("revisar", "subir") else "inicio"
    pendientes = len(ejemplo.con_diferencias(ejemplo.grupos(timezone.localdate())))
    return {"activa": activa, "n": pendientes}
