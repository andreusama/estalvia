import json
from types import SimpleNamespace

import pytest
from django.test import Client

from plataforma.settings_tests import CLAVE

# Documento SINTÉTICO (inventado): nada de datos reales en git (ADR 0001 del bar)
DATOS_FACTURA = {
    "tipo": "factura",
    "proveedor": {
        "nombre": "Distribuciones Ejemplo S.L.",
        "nif": "B00000000",
        "direccion": None,
        "iban": "ES00 0000 0000 0000 0000 0000",
    },
    "cliente": {"nombre": "Bar de Prueba", "nif": None},
    "numero": "F26-00001",
    "fecha": "2026-10-21",
    "vencimiento": "2026-10-21",
    "forma_pago": "Banco",
    "lineas": [
        {
            "codigo": "001",
            "descripcion": "BAYETA AZUL 10ud",
            "cantidad": "1",
            "unidad": None,
            "precio_unitario": "10.49",
            "descuento": None,
            "importe": "10.49",
        }
    ],
    "referencias_albaran": [{"numero": "A.00001", "fecha": "2026-10-21"}],
    "iva": [{"tipo": "21", "base": "10.49", "cuota": "2.20"}],
    "base_imponible": "10.49",
    "total": "12.69",
    "confianza": "media",
    "campos_dudosos": [{"campo": "numero", "linea": None, "motivo": "último dígito borroso"}],
    "avisos": ["Se ve el borde de otra hoja detrás"],
}


def respuesta_falsa(datos):
    return SimpleNamespace(
        stop_reason="end_turn",
        model="modelo-falso",
        content=[SimpleNamespace(type="text", text=json.dumps(datos))],
        usage=SimpleNamespace(input_tokens=1000, output_tokens=500),
    )


class ClienteFalso:
    def __init__(self, datos=None, error=None):
        self.llamadas = []
        self.messages = SimpleNamespace(create=self._crear)
        self._datos, self._error = datos, error

    def _crear(self, **kw):
        self.llamadas.append(kw)
        if self._error:
            raise self._error
        return respuesta_falsa(self._datos)


@pytest.fixture
def ia(monkeypatch):
    """Instala un cliente de IA falso; devuelve una función para configurarlo."""
    from prototipos.bar import extraccion

    def instalar(datos=None, error=None):
        cliente = ClienteFalso(datos, error)
        monkeypatch.setattr(extraccion, "crear_cliente", lambda: cliente)
        return cliente

    return instalar


@pytest.fixture
def web():
    c = Client(HTTP_HOST="localhost")
    c.post("/entrar/", {"password": CLAVE})
    return c


PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082"
)
