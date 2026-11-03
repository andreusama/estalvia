import pytest


@pytest.fixture(autouse=True)
def _nunca_la_ia_real(monkeypatch):
    """Los tests no llaman a la API: cada test que la necesite pone su cliente falso."""
    from prototipos.bar import extraccion

    def prohibido():
        raise AssertionError("Un test intentó llamar a la IA real")

    monkeypatch.setattr(extraccion, "crear_cliente", prohibido)
