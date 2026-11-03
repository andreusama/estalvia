from django.conf import settings
from django.db import models

from .numeros import normalizar_referencia


def _propietario():
    """Cada fila es de un usuario. Nulo solo en lo que existía antes de las cuentas (se asigna con `crear_usuario`)."""
    return models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+")


class Proveedor(models.Model):
    propietario = _propietario()
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

    propietario = _propietario()
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


class PerfilImportacion(models.Model):
    """Cómo leer el extracto de un banco: separador, formato de fecha y de números, y qué columna es cada cosa.

    No guarda credenciales del banco ni el número de cuenta completo: solo las últimas cifras, para reconocerla.
    """

    SEPARADORES = [("auto", "Detectarlo solo"), (";", "Punto y coma ( ; )"), (",", "Coma ( , )"), ("\t", "Tabulador")]
    FORMATOS_FECHA = [
        ("%d/%m/%Y", "31/12/2026"),
        ("%d-%m-%Y", "31-12-2026"),
        ("%Y-%m-%d", "2026-12-31"),
        ("%d/%m/%y", "31/12/26"),
        ("%d.%m.%Y", "31.12.2026"),
    ]
    MILES = [("", "Ninguno"), (".", "Punto ( 1.240,00 )"), (",", "Coma ( 1,240.00 )"), (" ", "Espacio ( 1 240,00 )")]
    DECIMALES = [(",", "Coma ( 1240,00 )"), (".", "Punto ( 1240.00 )")]

    propietario = _propietario()
    nombre = models.CharField(max_length=80, default="Mi banco")
    cuenta_final = models.CharField(max_length=4, blank=True)  # solo las últimas cifras
    separador = models.CharField(max_length=4, choices=SEPARADORES, default="auto")
    formato_fecha = models.CharField(max_length=10, choices=FORMATOS_FECHA, default="%d/%m/%Y")
    sep_miles = models.CharField(max_length=1, choices=MILES, default=".", blank=True)
    sep_decimal = models.CharField(max_length=1, choices=DECIMALES, default=",")
    col_fecha = models.CharField(max_length=80, default="Fecha")
    col_concepto = models.CharField(max_length=80, default="Concepto")
    col_concepto_aux = models.CharField(max_length=80, blank=True)  # si la principal está vacía
    col_importe = models.CharField(max_length=80, default="Importe")  # con signo: gastos negativos
    col_abono = models.CharField(max_length=80, blank=True)  # si el banco separa cargos (col_importe) y abonos
    col_saldo = models.CharField(max_length=80, blank=True, default="Saldo")

    def __str__(self):
        return self.nombre

    @classmethod
    def por_defecto(cls, usuario):
        return cls.objects.filter(propietario=usuario).first() or cls.objects.create(propietario=usuario)


class Movimiento(models.Model):
    """Una línea del extracto. Gasto = negativo, ingreso = positivo. Nunca se borra."""

    perfil = models.ForeignKey(PerfilImportacion, on_delete=models.PROTECT, related_name="movimientos")
    fecha = models.DateField(db_index=True)
    concepto = models.CharField(max_length=400)
    importe = models.DecimalField(max_digits=12, decimal_places=2)
    saldo = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    huella = models.CharField(max_length=64, unique=True)  # evita duplicados al reimportar el mismo extracto
    fichero = models.CharField(max_length=255, blank=True)
    fila = models.PositiveIntegerField(default=0)
    importado_en = models.DateTimeField(auto_now_add=True)
    ignorado_en = models.DateTimeField(null=True, blank=True)  # «ya lo he mirado»: se oculta de los avisos

    class Meta:
        ordering = ["fecha", "id"]

    def __str__(self):
        return f"{self.fecha} {self.concepto} {self.importe}"


class Pago(models.Model):
    """Una factura pagada, por un movimiento bancario confirmado o a mano en efectivo. Nunca se borra."""

    class Metodo(models.TextChoices):
        BANCO = "banco", "Banco"
        EFECTIVO = "efectivo", "Efectivo"

    documento = models.ForeignKey(Documento, on_delete=models.PROTECT, related_name="pagos")
    movimiento = models.OneToOneField(Movimiento, null=True, blank=True, on_delete=models.PROTECT, related_name="pago")
    importe = models.DecimalField(max_digits=12, decimal_places=2)
    metodo = models.CharField(max_length=10, choices=Metodo.choices)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["creado_en", "id"]
