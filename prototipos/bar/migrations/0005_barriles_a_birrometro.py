from django.db import migrations


def pasar_a_birrometro(apps, schema_editor):
    """El Birròmetro es otra herramienta: sus barriles pasan a su app. Cada barril antiguo tenía un solo tipo de
    ración, así que queda como una ración con las que salían enteras."""
    Viejo = apps.get_model("bar", "Barril")
    Barril, Racion = apps.get_model("birrometro", "Barril"), apps.get_model("birrometro", "RacionBarril")
    for b in Viejo.objects.all():
        nuevo = Barril.objects.create(
            propietario_id=b.propietario_id, marca=b.marca, litros=b.litros, fecha=b.fecha, precio=b.precio,
            merma=b.merma, iva_venta=b.iva_venta,
        )  # fmt: skip
        utiles = b.litros * (100 - b.merma) / 100
        Racion.objects.create(
            barril=nuevo, nombre="Ración", cl=b.servicio_cl, precio_venta=b.precio_venta,
            cantidad=int(utiles * 100 // b.servicio_cl),
        )  # fmt: skip


class Migration(migrations.Migration):
    """Solo copia datos. Se borra la tabla antigua en la 0006: en PostgreSQL no se puede hacer todo a la vez."""

    dependencies = [
        ("bar", "0004_barril"),
        ("birrometro", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(pasar_a_birrometro, migrations.RunPython.noop),
    ]
