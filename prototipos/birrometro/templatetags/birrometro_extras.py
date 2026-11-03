from django import template

from ..numeros import eur as _eur

register = template.Library()


@register.filter
def eur(valor):
    return _eur(valor)
