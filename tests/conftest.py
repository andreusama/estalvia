"""Los tests de la web nunca leen ni escriben las subidas reales de `data/private/` (consumo y facturas del dueño)."""
import pytest


@pytest.fixture(autouse=True)
def _sin_subidas_ni_cache_reales(tmp_path):
    from django.conf import settings
    if not settings.configured:  # tests que no tocan la web
        yield
        return
    from django.test import override_settings
    with override_settings(UPLOADS_DIR=str(tmp_path / "_uploads"), CACHE_DIR=str(tmp_path / "_cache")):
        yield
