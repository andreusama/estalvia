"""Grupos de ejemplo para las pantallas Resumen, Revisar y Detalle de la versión móvil.

DATOS INVENTADOS. La conciliación real (emparejar facturas con albaranes) todavía no existe: hasta que exista, estas
pantallas enseñan cómo quedarán con estos grupos, y la interfaz lo dice en pantalla. Cuando haya conciliación, basta con
que `grupos()` devuelva los grupos reales con esta misma forma. Aunque los datos sean de ejemplo, las cifras se calculan
en código con decimales exactos y sin tolerancia: nada se calcula con IA.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal as D

from .numeros import eur, num, redondear


@dataclass(frozen=True)
class LineaEj:
    descripcion: str
    cantidad: D
    precio: D
    unidad: str = "uds."

    @property
    def importe(self) -> D:
        return redondear(self.cantidad * self.precio)

    @property
    def calculo(self) -> str:
        """«25 uds. × 1,72 €»; vacío si es una sola unidad, porque el importe ya lo dice todo."""
        if self.cantidad == 1:
            return ""
        decimales = 0 if self.cantidad == self.cantidad.to_integral() else 2
        return f"{num(self.cantidad, decimales)} {self.unidad} × {eur(self.precio)}"


@dataclass(frozen=True)
class DocEj:
    numero: str
    fecha: date
    lineas: tuple[LineaEj, ...]

    @property
    def total(self) -> D:
        return sum((linea.importe for linea in self.lineas), D("0.00"))


@dataclass(frozen=True)
class ParLinea:
    numero: int
    albaran: LineaEj | None
    factura: LineaEj | None

    @property
    def difiere(self) -> bool:
        return self.albaran != self.factura


@dataclass(frozen=True)
class GrupoEj:
    id: str
    proveedor: str
    albaran: DocEj | None
    factura: DocEj | None
    hoy: date

    @property
    def estado(self) -> str:
        """ok = coincide al céntimo, diff = no coincide, wait = falta un documento. Sin tolerancia."""
        if self.albaran is None or self.factura is None:
            return "wait"
        iguales = self.albaran.lineas == self.factura.lineas and self.albaran.total == self.factura.total
        return "ok" if iguales else "diff"

    @property
    def diferencia(self) -> D | None:
        if self.albaran is None or self.factura is None:
            return None
        return self.factura.total - self.albaran.total

    @property
    def pares(self) -> list[ParLinea]:
        a = self.albaran.lineas if self.albaran else ()
        f = self.factura.lineas if self.factura else ()
        return [
            ParLinea(i + 1, a[i] if i < len(a) else None, f[i] if i < len(f) else None)
            for i in range(max(len(a), len(f)))
        ]

    @property
    def etiqueta(self) -> str:
        """Texto de la píldora: lo que ve el usuario sin abrir nada."""
        if self.estado == "ok":
            return "Coincide"
        if self.estado == "wait":
            return "Falta factura" if self.factura is None else "Falta albarán"
        return con_signo(self.diferencia)

    @property
    def simbolo(self) -> str:
        return {"ok": "=", "diff": "≠", "wait": "?"}[self.estado]

    @property
    def estado_texto(self) -> str:
        """Lo mismo que el símbolo, dicho con palabras (para lectores de pantalla)."""
        return {"ok": "Coincide", "diff": "No coincide", "wait": "Pendiente"}[self.estado]

    @property
    def etiqueta_detalle(self) -> str:
        if self.estado == "diff":
            return f"Diferencia de {eur(abs(self.diferencia))}"
        return self.etiqueta

    @property
    def nota(self) -> str:
        if self.estado == "ok":
            return "Coincide al céntimo."
        if self.estado == "wait":
            dias = (self.hoy - (self.albaran or self.factura).fecha).days
            return f"El albarán llegó hace {dias} días."
        malas = [p.numero for p in self.pares if p.difiere]
        sentido = "de más" if self.diferencia > 0 else "de menos"
        donde = f"la línea {malas[0]}" if len(malas) == 1 else "las líneas " + " y ".join(str(n) for n in malas)
        return f"La factura cobra {sentido} en {donde}."

    @property
    def explicacion(self) -> str:
        """Frase del detalle: qué línea difiere y en qué."""
        for p in self.pares:
            if not p.difiere:
                continue
            a, f = p.albaran, p.factura
            if a and f and a.cantidad == f.cantidad and a.precio != f.precio:
                return (
                    f"La factura cobra {eur(f.precio)} por unidad en la línea {p.numero}. "
                    f"El albarán indica {eur(a.precio)}."
                )
            if a and f and a.cantidad != f.cantidad:
                return (
                    f"La factura cuenta {num(f.cantidad, 0)} en la línea {p.numero} y el albarán {num(a.cantidad, 0)}."
                )
            return f"La línea {p.numero} no es igual en el albarán y en la factura."
        return ""

    @property
    def fechas(self) -> str:
        partes = []
        if self.albaran:
            partes.append(f"Albarán del {self.albaran.fecha.day} {MESES[self.albaran.fecha.month - 1]}")
        if self.factura:
            partes.append(f"Factura del {self.factura.fecha.day} {MESES[self.factura.fecha.month - 1]}")
        return " · ".join(partes)


MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def con_signo(valor: D) -> str:
    return ("+" if valor > 0 else "−") + eur(abs(valor))


def _g(hoy, id_, proveedor, alb, fac):
    """alb y fac: (número, días antes de hoy, [(descripción, cantidad, precio[, unidad])…]) o None."""

    def doc(d):
        if d is None:
            return None
        numero, dias, lineas = d
        return DocEj(numero, hoy - timedelta(days=dias), tuple(LineaEj(x[0], D(x[1]), D(x[2]), *x[3:]) for x in lineas))

    return GrupoEj(id_, proveedor, doc(alb), doc(fac), hoy)


def grupos(hoy: date) -> list[GrupoEj]:
    """Los grupos de ejemplo por urgencia: diferencias (de mayor a menor), pendientes y los que coinciden."""
    tornillos = ("Tornillo hexagonal M8, caja de 100", "1", "25.00")
    tacos = ("Taco de nailon 8 mm, bolsa", "1", "18.40")
    todos = [
        _g(
            hoy,
            "ferreteria-lleida",
            "Ferretería Lleida",
            ("0388", 21, [tornillos, tacos, ("Tornillería inox A2", "25", "1.72")]),
            ("F-1907", 15, [tornillos, tacos, ("Tornillería inox A2", "25", "2.22")]),
        ),
        _g(
            hoy,
            "maquinaria-pons",
            "Maquinaria Pons",
            ("0391", 19, [("Filtro de aceite", "4", "18.50"), ("Correa de transmisión", "1", "112.30")]),
            ("F-2210", 12, [("Filtro de aceite", "4", "18.50"), ("Correa de transmisión", "1", "176.50")]),
        ),
        _g(
            hoy,
            "piensos-noguera",
            "Piensos Noguera",
            ("0402", 10, [("Pienso de engorde, saco de 25 kg", "40", "14.50")]),
            ("F-0873", 6, [("Pienso de engorde, saco de 25 kg", "40", "15.05")]),
        ),
        _g(
            hoy,
            "quimica-urgell",
            "Química Agrícola Urgell",
            ("0395", 17, [("Herbicida, bidón de 5 l", "2", "31.20"), ("Guantes de nitrilo, pack", "1", "14.50")]),
            ("F-3318", 11, [("Herbicida, bidón de 5 l", "2", "31.20"), ("Guantes de nitrilo, pack", "1", "23.40")]),
        ),
        _g(
            hoy,
            "embalajes-balaguer",
            "Embalajes Balaguer",
            ("0407", 8, [("Cinta adhesiva, rollo", "10", "2.10")]),
            ("F-0614", 4, [("Cinta adhesiva, rollo", "10", "2.41")]),
        ),
        _g(
            hoy,
            "transportes-garrigues",
            "Transportes Garrigues",
            ("0419", 9, [("Transporte de palé", "1", "310.00")]),
            None,
        ),
        _g(
            hoy,
            "distribuciones-segre",
            "Distribuciones Segre",
            ("0377", 24, [("Aceite de oliva, garrafa de 5 l", "6", "21.90"), ("Sal fina, kg", "10", "2.29", "kg")]),
            ("F-0912", 20, [("Aceite de oliva, garrafa de 5 l", "6", "21.90"), ("Sal fina, kg", "10", "2.29", "kg")]),
        ),
        _g(
            hoy,
            "carnicas-cerdanya",
            "Cárnicas Cerdanya",
            ("0380", 14, [("Lomo de cerdo, kg", "18.5", "8.90", "kg"), ("Costilla, kg", "12", "6.40", "kg")]),
            ("F-0921", 9, [("Lomo de cerdo, kg", "18.5", "8.90", "kg"), ("Costilla, kg", "12", "6.40", "kg")]),
        ),
    ]
    orden = {"diff": 0, "wait": 1, "ok": 2}
    return sorted(
        todos, key=lambda g: (orden[g.estado], -abs(g.diferencia or 0), g.albaran.fecha if g.albaran else hoy)
    )


def resumen(lista: list[GrupoEj]) -> dict:
    """Las tres cifras del mes y el total por reclamar (solo lo que la factura cobra de más)."""
    n = {e: sum(1 for g in lista if g.estado == e) for e in ("ok", "diff", "wait")}
    por_reclamar = sum((g.diferencia for g in lista if g.estado == "diff" and g.diferencia > 0), D("0.00"))
    return {"ok": n["ok"], "diff": n["diff"], "wait": n["wait"], "por_reclamar": por_reclamar}


def con_diferencias(lista: list[GrupoEj]) -> list[GrupoEj]:
    return [g for g in lista if g.estado == "diff"]
