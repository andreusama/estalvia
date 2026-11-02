from django.db import models

from .numeros import normalizar_referencia


class Proveedor(models.Model):
    nombre = models.CharField(max_length=200)
    nif = models.CharField(max_length=20, blank=True, db_index=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name_plural = "proveedores"

    def __str__(self):
        return self.nombre


class Documento(models.Model):
    class Tipo(models.TextChoices):
        ALBARAN = "albaran", "Albarán"
        FACTURA = "factura", "Factura"
        TICKET = "ticket", "Ticket"
        ABONO = "abono", "Abono"
        DESCONOCIDO = "desconocido", "Sin identificar"

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Por leer"
        PROCESADO = "procesado", "Por revisar"
        ERROR = "error", "No se pudo leer"
        REVISADO = "revisado", "Revisado"

    # Archivo original: en la base de datos porque Vercel no tiene disco (ADR 0003 del bar)
    archivo = models.BinaryField(editable=False)
    nombre_archivo = models.CharField(max_length=255)
    tipo_mime = models.CharField(max_length=100)
    sha256 = models.CharField(max_length=64, db_index=True)

    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True)
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.DESCONOCIDO)

    proveedor = models.ForeignKey(
        Proveedor, null=True, blank=True, on_delete=models.SET_NULL, related_name="documentos"
    )
    proveedor_nombre = models.CharField(max_length=200, blank=True)
    proveedor_nif = models.CharField(max_length=20, blank=True)
    proveedor_iban = models.CharField(max_length=40, blank=True)
    cliente_nombre = models.CharField(max_length=200, blank=True)
    cliente_nif = models.CharField(max_length=20, blank=True)

    numero = models.CharField(max_length=60, blank=True)
    fecha = models.DateField(null=True, blank=True)
    vencimiento = models.DateField(null=True, blank=True)
    forma_pago = models.CharField(max_length=120, blank=True)
    base_imponible = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Lo que dijo la IA, sin tocar, para poder medirla y revisar el pasado
    confianza = models.CharField(max_length=5, blank=True)
    campos_dudosos = models.JSONField(default=list, blank=True)
    avisos = models.JSONField(default=list, blank=True)
    respuesta_ia = models.JSONField(null=True, blank=True)
    modelo_ia = models.CharField(max_length=60, blank=True)
    version_prompt = models.CharField(max_length=30, blank=True)
    error_texto = models.TextField(blank=True)

    subido_en = models.DateTimeField(auto_now_add=True)
    leido_en = models.DateTimeField(null=True, blank=True)
    revisado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-subido_en", "-id"]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.numero or self.nombre_archivo}"


class Linea(models.Model):
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name="lineas")
    orden = models.PositiveIntegerField(default=0)
    codigo = models.CharField(max_length=60, blank=True)
    descripcion = models.CharField(max_length=300, blank=True)
    cantidad = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    unidad = models.CharField(max_length=30, blank=True)
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    descuento = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)  # % impreso
    importe = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["orden", "id"]


class ReferenciaAlbaran(models.Model):
    """Albarán que cita una factura, tal como está impreso (A.28541, A-28541...)."""

    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name="referencias")
    numero = models.CharField(max_length=60)
    numero_normalizado = models.CharField(max_length=60, db_index=True)
    fecha = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["id"]

    def save(self, *args, **kwargs):
        self.numero_normalizado = normalizar_referencia(self.numero)
        super().save(*args, **kwargs)


class DesgloseIva(models.Model):
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name="desglose_iva")
    tipo = models.DecimalField(max_digits=5, decimal_places=2)  # 21,00
    base = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cuota = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["-tipo", "id"]


class Evento(models.Model):
    """Historia del documento: subido, leído, corregido, revisado. Nunca se borra."""

    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name="eventos")
    cuando = models.DateTimeField(auto_now_add=True)
    tipo = models.CharField(max_length=20)
    detalle = models.TextField(blank=True)

    class Meta:
        ordering = ["cuando", "id"]
