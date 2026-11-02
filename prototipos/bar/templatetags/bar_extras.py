from django import template

from ..numeros import eur as _eur

register = template.Library()


@register.filter
def eur(valor):
    return _eur(valor)


@register.filter
def get_item(diccionario, clave):
    """dudosos_lineas|get_item:3 → lista de motivos de la línea 3 (vacía si no hay)."""
    return diccionario.get(clave, [])
