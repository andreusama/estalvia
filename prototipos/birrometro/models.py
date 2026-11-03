from django.conf import settings
from django.db import models


class Barril(models.Model):
    """Un barril de cerveza comprado y cómo se reparte. Cada barril es de un usuario. Nunca se borra."""

    propietario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    marca = models.CharField(max_length=120)
    litros = models.DecimalField(max_digits=6, decimal_places=2)
    fecha = models.DateField()  # fecha de compra
    precio = models.DecimalField(max_digits=10, decimal_places=2)  # lo que cuesta el barril, sin IVA
    merma = models.DecimalField(max_digits=4, decimal_places=1, default=8)  # % que se pierde en espuma y derrames
    iva_venta = models.DecimalField(max_digits=4, decimal_places=1, default=10)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-id"]
        verbose_name_plural = "barriles"

    def __str__(self):
        return f"{self.marca} {self.litros} L ({self.fecha})"


class RacionBarril(models.Model):
    """Lo que se saca de un barril en un tipo de ración (zurito, caña, jarra): tamaño, precio y cuántas."""

    barril = models.ForeignKey(Barril, on_delete=models.CASCADE, related_name="raciones")
    orden = models.PositiveSmallIntegerField(default=0)
    nombre = models.CharField(max_length=30)
    cl = models.PositiveSmallIntegerField()
    precio_venta = models.DecimalField(max_digits=6, decimal_places=2)  # con IVA
    cantidad = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["orden", "id"]
