from decimal import Decimal

from django import forms

from . import calculo
from .calculo import IVAS, TIPOS
from .numeros import a_decimal, num


class ImporteField(forms.CharField):
    """Número escrito a la española (12,50) o con punto. Se guarda como Decimal; nada se calcula aquí."""

    def __init__(self, **kw):
        kw.setdefault("required", True)
        kw.setdefault("widget", forms.TextInput(attrs={"inputmode": "decimal", "autocomplete": "off"}))
        super().__init__(**kw)

    def prepare_value(self, value):
        return num(value, 2) if isinstance(value, Decimal) else value

    def to_python(self, value):
        if value in self.empty_values:
            return None
        d = a_decimal(value)
        if d is None:
            raise forms.ValidationError("Escribe un número, por ejemplo 12,50.")
        return d


class BarrilForm(forms.Form):
    """Los datos del Birròmetro. Valida y convierte; las cuentas las hace `calculo.calcular`.

    Por cada tipo de ración (zurito, caña, jarra) hay tres campos: `<tipo>_cl`, `<tipo>_pvp` y `<tipo>_n`.
    """

    marca = forms.CharField(max_length=120, label="Marca")
    litros = ImporteField(label="Litros del barril")
    fecha = forms.DateField(label="Fecha de compra", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    precio = ImporteField(label="Precio del barril (sin IVA)")
    merma = ImporteField(label="Merma (%)")
    iva_venta = forms.TypedChoiceField(choices=IVAS, coerce=Decimal, label="IVA de lo que vendes")

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        for clave, nombre, _, _ in TIPOS:
            self.fields[f"{clave}_cl"] = forms.IntegerField(min_value=5, max_value=100, label=f"{nombre}: centilitros")
            self.fields[f"{clave}_pvp"] = ImporteField(label=f"{nombre}: precio de venta")
            self.fields[f"{clave}_n"] = forms.IntegerField(
                min_value=0, max_value=2000, required=False, label=f"{nombre}: cuántas sacas"
            )
        for campo in self.fields.values():
            campo.widget.attrs.setdefault("class", "field")
        for clave, *_ in TIPOS:
            self.fields[f"{clave}_pvp"].widget.attrs.pop("class", None)

    def _entre(self, nombre, minimo, maximo, texto):
        valor = self.cleaned_data.get(nombre)
        if valor is not None and not (minimo <= valor <= maximo):
            raise forms.ValidationError(texto)
        return valor

    def clean_litros(self):
        return self._entre("litros", Decimal("1"), Decimal("200"), "Un barril tiene entre 1 y 200 litros.")

    def clean_precio(self):
        return self._entre("precio", Decimal("0.01"), Decimal("5000"), "Escribe lo que cuesta el barril, sin IVA.")

    def clean_merma(self):
        return self._entre("merma", Decimal("0"), Decimal("40"), "La merma va del 0 al 40 %.")

    def clean(self):
        datos = super().clean()
        for clave, nombre, _, _ in TIPOS:
            pvp = datos.get(f"{clave}_pvp")
            if pvp is not None and not (Decimal("0.10") <= pvp <= Decimal("50")):
                self.add_error(f"{clave}_pvp", f"{nombre}: el precio va de 0,10 a 50 €.")
            if f"{clave}_n" in datos and datos[f"{clave}_n"] is None:
                datos[f"{clave}_n"] = 0  # en blanco = no sacas ninguna
        if self.errors:
            return datos
        sale = calculo.litros_de(self.raciones())
        hay = calculo.litros_utiles(datos["litros"], datos["merma"])
        if sale > hay:
            raise forms.ValidationError(
                f"Te pasas: has repartido {num(sale, 2)} L y de este barril solo se pueden servir {num(hay, 2)} L "
                f"(después de la merma). Saca menos raciones."
            )
        return datos

    def raciones(self) -> list[calculo.Racion]:
        d = self.cleaned_data
        return [
            calculo.Racion(nombre, d[f"{clave}_cl"], d[f"{clave}_pvp"], d[f"{clave}_n"] or 0)
            for clave, nombre, _, _ in TIPOS
        ]
