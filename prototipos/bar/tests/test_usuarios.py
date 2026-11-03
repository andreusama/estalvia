"""Cada cuenta ve solo lo suyo: documentos, facturas, extracto y pagos. Dos usuarios SINTÉTICOS, ana y beto."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command

from prototipos.bar import extracto, pagos, panel
from prototipos.bar.models import Documento, Movimiento, Pago, PerfilImportacion, Proveedor
from prototipos.bar.tests.conftest import PNG, cliente_de, usuario
from prototipos.bar.tests.test_pagos import EXTRACTO, factura

pytestmark = pytest.mark.django_db


def test_un_usuario_no_ve_los_documentos_del_otro():
    ana, beto = cliente_de("ana"), cliente_de("beto")
    d = factura(propietario=usuario("ana"))
    assert ana.get(f"/bar/documentos/{d.pk}/").status_code == 200
    for url in (f"/bar/documentos/{d.pk}/", f"/bar/documentos/{d.pk}/archivo/", f"/bar/documentos/{d.pk}/confirmar/"):
        assert beto.get(url).status_code == 404
    assert beto.post(f"/bar/documentos/{d.pk}/leer/").status_code == 404
    assert "F26-00001" in ana.get("/bar/").content.decode()
    assert "F26-00001" not in beto.get("/bar/").content.decode()


def test_el_mismo_archivo_lo_pueden_subir_dos_usuarios():
    for nombre in ("ana", "beto"):
        c = cliente_de(nombre)
        r = c.post(
            "/bar/subir/",
            {"archivo": SimpleUploadedFile("f.png", PNG, "image/png")},
            headers={"X-Requested-With": "fetch"},
        )
        assert r.json()["nuevo"] is True
    assert Documento.objects.count() == 2
    assert set(Documento.objects.values_list("propietario__username", flat=True)) == {"ana", "beto"}


def test_el_extracto_y_las_facturas_de_uno_no_aparecen_en_los_pagos_del_otro():
    ana, beto = usuario("ana"), usuario("beto")
    factura(propietario=ana)
    extracto.importar_extracto(PerfilImportacion.por_defecto(ana), "oct.csv", EXTRACTO.encode())
    assert pagos.movimientos_por_mirar(beto) == [] and pagos.facturas(beto) == []
    assert panel.cifras(beto)["contador"] == 0 and panel.cifras(ana)["contador"] > 0
    html = cliente_de("beto").get("/bar/pagos/").content.decode()
    assert "TRANSF A DISTRIBUCIONES" not in html and "F26-00001" not in html


def test_beto_no_puede_confirmar_ignorar_ni_pagar_lo_de_ana():
    ana, beto = usuario("ana"), cliente_de("beto")
    f = factura(propietario=ana)
    extracto.importar_extracto(PerfilImportacion.por_defecto(ana), "oct.csv", EXTRACTO.encode())
    mov = Movimiento.objects.filter(importe=-12.69).first()
    assert beto.post(f"/bar/pagos/confirmar/{mov.pk}/").status_code == 404
    assert beto.post(f"/bar/pagos/ignorar/{mov.pk}/").status_code == 404
    assert beto.post(f"/bar/pagos/efectivo/{f.pk}/").status_code == 404
    mov.refresh_from_db()
    assert not Pago.objects.exists() and mov.ignorado_en is None


def test_cada_uno_tiene_su_formato_de_banco_y_sus_proveedores():
    ana, beto = usuario("ana"), usuario("beto")
    a, b = PerfilImportacion.por_defecto(ana), PerfilImportacion.por_defecto(beto)
    assert a.pk != b.pk and PerfilImportacion.por_defecto(ana).pk == a.pk
    cliente_de("ana").post(
        "/bar/pagos/formato/",
        {
            **{
                k: getattr(a, k)
                for k in (
                    "nombre",
                    "separador",
                    "formato_fecha",
                    "sep_miles",
                    "sep_decimal",
                    "col_fecha",
                    "col_concepto",
                    "col_importe",
                    "col_saldo",
                )
            },
            "nombre": "Banco de Ana",
            "cuenta_final": "",
        },
    )
    b.refresh_from_db()
    assert b.nombre == "Mi banco"
    # El proveedor de Ana no se reutiliza para Beto aunque se llamen igual
    from prototipos.bar import servicios

    da, db = factura(propietario=ana, numero="A-1"), factura(propietario=beto, numero="B-1")
    servicios.vincular_proveedor(da)
    servicios.vincular_proveedor(db)
    assert da.proveedor_id != db.proveedor_id and Proveedor.objects.count() == 2


def test_crear_usuario_adopta_los_datos_de_antes_de_las_cuentas(monkeypatch):
    huerfano = Documento.objects.create(archivo=b"x", nombre_archivo="v.png", tipo_mime="image/png", sha256="viejo")
    assert huerfano.propietario is None
    assert panel.cifras(usuario("ana"))["por_revisar"] == 0  # nadie lo ve mientras no sea de alguien
    claves = iter(["una-clave-larga-1"] * 2)
    monkeypatch.setattr("plataforma.management.commands.crear_usuario.getpass", lambda _: next(claves))
    call_command("crear_usuario", "carlos", "--adoptar")
    huerfano.refresh_from_db()
    assert huerfano.propietario.username == "carlos"
