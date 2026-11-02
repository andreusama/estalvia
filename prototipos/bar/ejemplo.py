"""DATOS DE EJEMPLO, inventados. Se sustituirán por los documentos revisados de la base de datos."""

from decimal import Decimal as D

from .grupos import Documento, Grupo

GRUPOS_EJEMPLO = [
    Grupo("Frutas Mari", Documento("Albarán", "A-0377", D("318.40")), Documento("Factura", "F-0415", D("324.40"))),
    Grupo(
        "Carnes El Pastor", Documento("Albarán", "A-3302", D("220.15")), None, nota_extra="Entregado el 30 de octubre."
    ),
    Grupo(
        "Cervezas Levante", Documento("Albarán", "A-8841", D("1248.60")), Documento("Factura", "F-2231", D("1248.60"))
    ),
    Grupo(
        "Distribuciones Gómez", Documento("Albarán", "A-1190", D("540.00")), Documento("Factura", "G-5520", D("540.00"))
    ),
]
