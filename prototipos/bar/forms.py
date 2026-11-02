from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory

from .models import DesgloseIva, Documento, Linea, PerfilImportacion, ReferenciaAlbaran
from .numeros import a_decimal, num


class ImporteField(forms.CharField):
    """Importe escrito a la española (12,50) o con punto. Se guarda como Decimal; nada se calcula aquí."""

    def __init__(self, *, minimo=2, maximo=2, **kw):
        self.minimo, self.maximo = minimo, maximo
        kw.setdefault("required", False)
        kw.setdefault("widget", forms.TextInput(attrs={"inputmode": "decimal", "autocomplete": "off"}))
        super().__init__(**kw)

    def prepare_value(self, value):
        if isinstance(value, Decimal):
            usados = -value.normalize().as_tuple().exponent
            return num(value, min(self.maximo, max(self.minimo, usados)))
        return value

    def to_python(self, value):
        if value in self.empty_values:
            return None
        d = a_decimal(value)
        if d is None:
            raise forms.ValidationError("Escribe un número, por ejemplo 12,50.")
        return d

    def has_changed(self, initial, data):
        return (initial if isinstance(initial, Decimal) else a_decimal(initial)) != a_decimal(data)


def _estilo(form):
    for campo in form.fields.values():
        if not isinstance(campo.widget, forms.CheckboxInput):
            campo.widget.attrs.setdefault("class", "field")


class DocumentoForm(forms.ModelForm):
    base_imponible = ImporteField()
    total = ImporteField()

    class Meta:
        model = Documento
        fields = [
            "tipo",
            "proveedor_nombre",
            "proveedor_nif",
            "proveedor_iban",
            "cliente_nombre",
            "cliente_nif",
            "numero",
            "fecha",
            "vencimiento",
            "forma_pago",
            "base_imponible",
            "total",
        ]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "vencimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        for nombre in self.fields:
            self.fields[nombre].required = nombre == "tipo"
        _estilo(self)


class LineaForm(forms.ModelForm):
    cantidad = ImporteField(minimo=0, maximo=3)
    precio_unitario = ImporteField(minimo=2, maximo=4)
    descuento = ImporteField(minimo=0, maximo=2)
    importe = ImporteField()

    class Meta:
        model = Linea
        fields = ["descripcion", "codigo", "cantidad", "unidad", "precio_unitario", "descuento", "importe"]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        for campo in ("descripcion", "codigo", "unidad"):
            self.fields[campo].required = False
        _estilo(self)


class IvaForm(forms.ModelForm):
    tipo = ImporteField(minimo=0, maximo=2, required=True)
    base = ImporteField()
    cuota = ImporteField()

    class Meta:
        model = DesgloseIva
        fields = ["tipo", "base", "cuota"]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        _estilo(self)


class ReferenciaForm(forms.ModelForm):
    class Meta:
        model = ReferenciaAlbaran
        fields = ["numero", "fecha"]
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["fecha"].required = False
        _estilo(self)


LineaFormSet = inlineformset_factory(Documento, Linea, form=LineaForm, extra=1, can_delete=True)
IvaFormSet = inlineformset_factory(Documento, DesgloseIva, form=IvaForm, extra=1, can_delete=True)
ReferenciaFormSet = inlineformset_factory(Documento, ReferenciaAlbaran, form=ReferenciaForm, extra=1, can_delete=True)


class PerfilImportacionForm(forms.ModelForm):
    """Cómo lee la aplicación el extracto de tu banco. Sin contraseñas ni número de cuenta completo."""

    class Meta:
        model = PerfilImportacion
        fields = [
            "nombre", "cuenta_final", "separador", "formato_fecha", "sep_miles", "sep_decimal",
            "col_fecha", "col_concepto", "col_concepto_aux", "col_importe", "col_abono", "col_saldo",
        ]  # fmt: skip
        labels = {
            "nombre": "Nombre del banco",
            "cuenta_final": "Últimas 4 cifras de la cuenta (opcional)",
            "separador": "Separador de columnas",
            "formato_fecha": "Formato de fecha",
            "sep_miles": "Separador de miles",
            "sep_decimal": "Separador de decimales",
            "col_fecha": "Columna de la fecha",
            "col_concepto": "Columna del concepto",
            "col_concepto_aux": "Columna del concepto de reserva (opcional)",
            "col_importe": "Columna del importe (o de los cargos)",
            "col_abono": "Columna de abonos (solo si el banco separa cargos y abonos)",
            "col_saldo": "Columna del saldo (opcional)",
        }

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        _estilo(self)

    def clean_cuenta_final(self):
        cifras = self.cleaned_data["cuenta_final"].strip()
        if cifras and not (cifras.isdigit() and len(cifras) == 4):
            raise forms.ValidationError("Escribe solo las 4 últimas cifras de la cuenta, o déjalo vacío.")
        return cifras

    def clean(self):
        datos = super().clean()
        if datos.get("sep_miles") and datos.get("sep_miles") == datos.get("sep_decimal"):
            raise forms.ValidationError("El separador de miles y el de decimales no pueden ser el mismo.")
        return datos
