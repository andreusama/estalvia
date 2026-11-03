"""Los barriles guardados cuando el Birròmetro estaba dentro del Bar pasan a su app sin perder nada."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_un_barril_del_bar_pasa_al_birrometro_con_una_racion_de_las_que_salian_enteras():
    antes = [("bar", "0004_barril")]
    ejecutor = MigrationExecutor(connection)
    ejecutor.migrate(antes)
    viejo = ejecutor.loader.project_state(antes).apps
    u = viejo.get_model("auth", "User").objects.create(username="ana")
    viejo.get_model("bar", "Barril").objects.create(
        propietario=u, marca="Prueba", litros="30", fecha="2026-10-01", precio="90.00", precio_venta="2.50",
        servicio_cl=20, merma="8", iva_venta="10",
    )  # fmt: skip

    despues = [("bar", "0006_quitar_barriles"), ("birrometro", "0001_initial")]
    ejecutor = MigrationExecutor(connection)
    ejecutor.migrate(despues)
    nuevo = ejecutor.loader.project_state(despues).apps
    b = nuevo.get_model("birrometro", "Barril").objects.get()
    r = b.raciones.get()
    assert (b.marca, b.propietario_id, str(b.precio)) == ("Prueba", u.pk, "90.00")
    assert (r.cl, str(r.precio_venta), r.cantidad) == (20, "2.50", 138)
