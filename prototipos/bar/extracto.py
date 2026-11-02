"""Leer el extracto del banco (CSV) y guardar los movimientos sin duplicarlos.

Todo lo hace el código, con decimales exactos; la IA no interviene y el extracto no sale de la aplicación. Cada fila que
no se entiende se devuelve como error con su número de línea: nunca se descarta en silencio.
"""

import csv
import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from django.db import transaction

from .models import Movimiento, PerfilImportacion


class ExtractoNoValido(Exception):
    """El fichero no se puede leer con este perfil (falta una columna, está vacío...). El mensaje es para el usuario."""


@dataclass(frozen=True)
class FilaExtracto:
    linea: int  # número de línea en el fichero, para poder avisar
    fecha: date
    concepto: str
    importe: Decimal  # gasto negativo, ingreso positivo
    saldo: Decimal | None


@dataclass(frozen=True)
class ErrorFila:
    linea: int
    motivo: str


@dataclass
class Lectura:
    filas: list[FilaExtracto] = field(default_factory=list)
    errores: list[ErrorFila] = field(default_factory=list)


@dataclass
class Resultado:
    nuevos: int
    repetidos: int
    errores: list[ErrorFila]


MAX_BYTES = 2 * 1024 * 1024  # un extracto de varios meses cabe de sobra; Vercel limita el cuerpo a 4,5 MB


def _decodificar(contenido: bytes) -> str:
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            return contenido.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return contenido.decode("latin-1")


def _separador(perfil: PerfilImportacion, texto: str) -> str:
    if perfil.separador != "auto":
        return perfil.separador
    cabecera = next((linea for linea in texto.splitlines() if linea.strip()), "")
    return max((";", ",", "\t"), key=cabecera.count)


def _clave(nombre: str) -> str:
    return " ".join((nombre or "").split()).casefold()


def leer_importe(texto: str, perfil: PerfilImportacion) -> Decimal | None:
    """«-1.240,50», «(12,50)», «12,50-» o «1 240,50 €» → Decimal exacto. Vacío → None; si no, ValueError."""
    t = (texto or "").replace("\xa0", " ").replace("€", "").replace("EUR", "").strip()
    if not t:
        return None
    negativo = t.startswith("(") and t.endswith(")")
    t = t.strip("()").strip()
    if t.endswith("-"):
        negativo, t = True, t[:-1].strip()
    if t.startswith("-"):
        negativo, t = True, t[1:].strip()
    elif t.startswith("+"):
        t = t[1:].strip()
    dec = re.escape(perfil.sep_decimal)
    simple = rf"\d+({dec}\d+)?"
    agrupado = rf"\d{{1,3}}({re.escape(perfil.sep_miles)}\d{{3}})+({dec}\d+)?" if perfil.sep_miles else simple
    if not (re.fullmatch(simple, t) or re.fullmatch(agrupado, t)):
        raise ValueError(f"«{texto.strip()}» no es un importe con el formato de números elegido")
    if perfil.sep_miles:
        t = t.replace(perfil.sep_miles, "")
    t = t.replace(perfil.sep_decimal, ".")
    valor = Decimal(t)
    if valor != valor.quantize(Decimal("0.01")):
        raise ValueError(f"«{texto.strip()}» tiene más de dos decimales; revisa el formato de números del banco")
    return -valor if negativo else valor


def leer_extracto(contenido: bytes, perfil: PerfilImportacion) -> Lectura:
    if not contenido.strip():
        raise ExtractoNoValido("El fichero está vacío.")
    texto = _decodificar(contenido)
    separador = _separador(perfil, texto)
    obligatorias = {"fecha": perfil.col_fecha, "concepto": perfil.col_concepto, "importe": perfil.col_importe}
    lineas = texto.splitlines()

    # Algunos bancos escriben líneas de título antes de la cabecera: se busca la primera que trae las columnas.
    indice = None
    for i, linea in enumerate(lineas[:40]):
        nombres = {_clave(c) for c in next(csv.reader([linea], delimiter=separador), [])}
        if all(_clave(c) in nombres for c in obligatorias.values()):
            indice = i
            break
    if indice is None:
        primera = next(csv.reader([lineas[0]], delimiter=separador), [])
        raise ExtractoNoValido(
            "No encuentro las columnas "
            + ", ".join(f"«{c}»" for c in obligatorias.values())
            + f". El fichero trae: {', '.join(c.strip() for c in primera)}. Ajusta el formato del banco."
        )

    lector = csv.reader(lineas[indice:], delimiter=separador)
    cabecera = [_clave(c) for c in next(lector)]

    def posicion(nombre: str) -> int | None:
        return cabecera.index(_clave(nombre)) if nombre and _clave(nombre) in cabecera else None

    p_fecha, p_concepto, p_importe = (
        posicion(perfil.col_fecha),
        posicion(perfil.col_concepto),
        posicion(perfil.col_importe),
    )
    p_aux, p_abono, p_saldo = posicion(perfil.col_concepto_aux), posicion(perfil.col_abono), posicion(perfil.col_saldo)
    if perfil.col_abono and p_abono is None:
        raise ExtractoNoValido(f"No encuentro la columna de abonos «{perfil.col_abono}».")

    lectura = Lectura()

    def celda(fila, p):
        return fila[p].strip() if p is not None and p < len(fila) else ""

    for n, fila in enumerate(lector, start=indice + 2):
        if not any(c.strip() for c in fila):
            continue
        try:
            try:
                fecha = datetime.strptime(celda(fila, p_fecha), perfil.formato_fecha).date()
            except ValueError:
                raise ValueError(f"«{celda(fila, p_fecha)}» no es una fecha con el formato elegido") from None
            cargo = leer_importe(celda(fila, p_importe), perfil)
            if p_abono is not None:  # cargos y abonos en dos columnas: el cargo se escribe en positivo
                abono = leer_importe(celda(fila, p_abono), perfil)
                if cargo is None and abono is None:
                    raise ValueError("no trae importe")
                importe = (abono or Decimal(0)) - abs(cargo or Decimal(0))
            else:
                if cargo is None:
                    raise ValueError("no trae importe")
                importe = cargo
            concepto = " ".join((celda(fila, p_concepto) or celda(fila, p_aux)).split())
            saldo = leer_importe(celda(fila, p_saldo), perfil) if p_saldo is not None else None
        except ValueError as e:
            lectura.errores.append(ErrorFila(n, str(e)))
            continue
        lectura.filas.append(FilaExtracto(n, fecha, concepto, importe, saldo))
    return lectura


def _huella(perfil_id: int, fila: FilaExtracto, repeticion: int) -> str:
    """Identifica un movimiento. Dos filas iguales el mismo día (mismo concepto, importe y saldo) se distinguen por su
    orden de aparición, así que un cobro doble real no se pierde y reimportar el mismo fichero no duplica nada."""
    clave = "|".join(
        [
            str(perfil_id),
            fila.fecha.isoformat(),
            fila.concepto.casefold(),
            str(fila.importe),
            str(fila.saldo),
            str(repeticion),
        ]
    )
    return hashlib.sha256(clave.encode()).hexdigest()


def importar_extracto(perfil: PerfilImportacion, nombre: str, contenido: bytes) -> Resultado:
    if len(contenido) > MAX_BYTES:
        raise ExtractoNoValido("El fichero pesa demasiado para ser un extracto. Descarga un periodo más corto.")
    lectura = leer_extracto(contenido, perfil)
    vistas: dict[tuple, int] = {}
    candidatos = []
    for fila in lectura.filas:
        clave = (fila.fecha, fila.concepto.casefold(), fila.importe, fila.saldo)
        vistas[clave] = vistas.get(clave, 0) + 1
        candidatos.append((_huella(perfil.pk, fila, vistas[clave]), fila))
    with transaction.atomic():
        existentes = set(
            Movimiento.objects.filter(huella__in=[h for h, _ in candidatos]).values_list("huella", flat=True)
        )
        nuevos = [
            Movimiento(
                perfil=perfil,
                fecha=f.fecha,
                concepto=f.concepto[:400],
                importe=f.importe,
                saldo=f.saldo,
                huella=h,
                fichero=nombre[:255],
                fila=f.linea,
            )
            for h, f in candidatos
            if h not in existentes
        ]
        Movimiento.objects.bulk_create(nuevos)
    return Resultado(len(nuevos), len(candidatos) - len(nuevos), lectura.errores)
