"""Pagos: qué movimiento del banco paga qué factura y qué no encaja. Facturas y extractos SINTÉTICOS."""

from datetime import date
from decimal import Decimal as D

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from prototipos.bar import extracto, pagos
from prototipos.bar.models import Documento, Movimiento, Pago, PerfilImportacion
from prototipos.bar.tests.conftest import usuario

pytestmark = pytest.mark.django_db

PROV = "Distribuciones Ejemplo S.L."
EXTRACTO = (
    "Fecha;Concepto;Importe;Saldo\n"
    "01/10/2026;TPV VENTAS TARJETAS 01/10;1.184,30;5.434,30\n"
    "05/10/2026;RECIBO LUZ LOCAL;-312,45;5.121,85\n"
    "28/10/2026;TRANSF A DISTRIBUCIONES EJEMPLO SL FRA F26-00001;-12,69;5.109,16\n"
    "28/10/2026;TRANSF A DISTRIBUCIONES EJEMPLO SL FRA F26-00001;-12,69;5.096,47\n"
    "29/10/2026;COMPRA ONLINE TIENDA OTRA;-12,69;5.083,78\n"
    "30/10/2026;RECIBO DISTRIBUCIONES EJEMPLO SL;-12,96;5.070,82\n"
    "31/10/2026;TRANSF A DISTRIBUCIONES EJEMPLO SL FRA F26-00999;-86,40;4.984,42\n"
    "02/11/2026;DEVOLUCION DISTRIBUCIONES EJEMPLO SL ABONO;12,69;4.997,11\n"
)


def factura(numero="F26-00001", total="12.69", proveedor=PROV, estado=Documento.Estado.REVISADO, **kw):
    propietario = kw.pop("propietario", None) or usuario()
    return Documento.objects.create(
        propietario=propietario, archivo=b"x", nombre_archivo="f.png", tipo_mime="image/png", sha256=numero,
        tipo=Documento.Tipo.FACTURA, estado=estado, proveedor_nombre=proveedor, numero=numero, total=D(total),
        fecha=date(2026, 10, 21), **kw,
    )  # fmt: skip


def analizar():
    return pagos.analizar(pagos.movimientos_por_mirar(usuario()), pagos.facturas(usuario()))


def importar(texto=EXTRACTO):
    return extracto.importar_extracto(PerfilImportacion.por_defecto(usuario()), "oct.csv", texto.encode())


def tipos():
    return [(v.movimiento.fecha.day, v.tipo) for v in analizar()]


def test_los_casos_del_extracto_de_prueba():
    factura()
    importar()
    assert tipos() == [
        (28, pagos.EXACTO),  # cita la factura y el importe coincide al céntimo
        (28, pagos.DOBLE),  # segundo cobro idéntico
        (30, pagos.DISTINTO),  # mismo proveedor, 12,96 en vez de 12,69
        (31, pagos.SIN_FACTURA),  # cita una factura que no está subida
        (2, pagos.DEVOLUCION),  # entra dinero del proveedor
    ]  # ventas, luz y alquiler no aparecen: no tienen que ver con proveedores


def test_solo_el_importe_identico_se_propone_para_confirmar():
    factura()
    importar()
    v = {x.movimiento.fecha.day: x for x in analizar() if x.movimiento.fecha.day != 28}
    assert [x.confirmable for x in analizar()] == [True, False, False, False, False]
    assert "0,27" in v[30].texto and "No se da por pagada" in v[30].texto
    assert "F26-00999" in v[31].texto and "Sube la factura" in v[31].texto


def test_sin_tolerancia_un_centimo_de_diferencia_nunca_se_propone():
    factura(total="12.70")
    importar("Fecha;Concepto;Importe;Saldo\n28/10/2026;TRANSF A DISTRIBUCIONES EJEMPLO SL FRA F26-00001;-12,69;1,00\n")
    (v,) = analizar()
    assert (v.tipo, v.confirmable) == (pagos.DISTINTO, False)


def test_propone_por_proveedor_e_importe_aunque_el_concepto_no_cite_la_factura():
    factura(total="86.40")
    importar("Fecha;Concepto;Importe;Saldo\n30/10/2026;RECIBO DISTRIBUCIONES EJEMPLO;-86,40;1,00\n")
    (v,) = analizar()
    assert v.tipo == pagos.EXACTO and "no cita el número" in v.texto


def test_mismo_importe_de_otra_tienda_es_solo_una_pista_nunca_un_pago():
    factura()
    importar("Fecha;Concepto;Importe;Saldo\n29/10/2026;COMPRA ONLINE TIENDA OTRA;-12,69;1,00\n")
    (v,) = analizar()
    assert (v.tipo, v.confirmable) == (pagos.PISTA, False) and "no nombra al proveedor" in v.texto


def test_una_referencia_demasiado_corta_no_empareja_cualquier_cosa():
    factura(numero="12")
    importar("Fecha;Concepto;Importe;Saldo\n28/10/2026;COMPRA 12 ARTICULOS;-12,69;1,00\n")
    assert [v.tipo for v in analizar()] == [pagos.PISTA]  # mismo importe pero sin referencia ni proveedor


def test_confirmar_deja_la_factura_pagada_y_un_segundo_cobro_pasa_a_doble():
    f = factura()
    importar()
    primero = analizar()[0]
    pagos.confirmar_pago(primero.movimiento, f)
    f = pagos.facturas(usuario())[0]
    assert f.esta_pagada and f.pagado == D("12.69")
    assert (28, pagos.DOBLE) in tipos() and (28, pagos.EXACTO) not in tipos()
    assert f.eventos.filter(tipo="pagado").exists()


def test_pagada_en_efectivo_cubre_lo_que_falta():
    f = factura()
    pagos.pagar_en_efectivo(f)
    assert pagos.facturas(usuario())[0].esta_pagada and Pago.objects.get().metodo == Pago.Metodo.EFECTIVO


def test_un_proveedor_con_palabras_comunes_no_se_confunde():
    assert pagos.proveedor_en("RECIBO DISTRIBUCIONES EJEMPLO SL", [PROV]) == PROV
    assert pagos.proveedor_en("PAGO DISTRIBUCIONES OTRO", [PROV]) == ""
    assert pagos.factura_citada("TRANSF FRA F26-24410") == "F26-24410"


# ---- Pantallas ----


def subir_extracto(web, texto=EXTRACTO):
    f = SimpleUploadedFile("extracto.csv", texto.encode(), content_type="text/csv")
    return web.post("/bar/pagos/importar/", {"extracto": f})


def test_importar_y_ver_propuestas_avisos_y_facturas_sin_pagar(web):
    factura()
    r = subir_extracto(web)
    assert r.status_code == 302 and "importados=8" in r["Location"]
    html = web.get("/bar/pagos/?importados=8&repetidos=0").content.decode()
    assert "Por confirmar" in html and "Avisos" in html and "Facturas sin pagar" in html
    assert "Posible cobro doble" in html and "Pago sin factura" in html
    assert "8 movimientos nuevos" in html
    assert "Provisional" not in html  # la factura de la prueba está revisada
    # reimportar no duplica
    assert "importados=0&repetidos=8" in subir_extracto(web)["Location"]
    assert Movimiento.objects.count() == 8


def test_confirmar_un_pago_desde_la_pantalla(web):
    f = factura()
    subir_extracto(web)
    mov = analizar()[0].movimiento
    assert web.post(f"/bar/pagos/confirmar/{mov.pk}/")["Location"].endswith("hecho=confirmado")
    assert Pago.objects.get().documento == f
    assert "Pagadas" in web.get("/bar/pagos/").content.decode()
    assert web.post(f"/bar/pagos/confirmar/{mov.pk}/").status_code == 404  # ya está confirmado


def test_no_se_puede_confirmar_a_la_fuerza_un_movimiento_que_no_es_exacto(web):
    factura()
    subir_extracto(web)
    distinto = next(v for v in analizar() if v.tipo == pagos.DISTINTO)
    r = web.post(f"/bar/pagos/confirmar/{distinto.movimiento.pk}/")
    assert r["Location"].endswith("hecho=no_valido") and not Pago.objects.exists()


def test_marcar_efectivo_y_ya_lo_he_mirado(web):
    f = factura()
    subir_extracto(web)
    aviso = next(v for v in analizar() if v.tipo == pagos.SIN_FACTURA)
    web.post(f"/bar/pagos/ignorar/{aviso.movimiento.pk}/")
    assert aviso.movimiento.pk not in [v.movimiento.pk for v in analizar()]
    Movimiento.objects.get(pk=aviso.movimiento.pk)  # no se borra nunca
    assert web.post(f"/bar/pagos/efectivo/{f.pk}/")["Location"].endswith("hecho=efectivo")
    assert web.post(f"/bar/pagos/efectivo/{f.pk}/").status_code == 404  # ya está pagada


def test_un_extracto_que_no_encaja_explica_por_que(web):
    r = web.post("/bar/pagos/importar/", {"extracto": SimpleUploadedFile("x.csv", b"Dia;Cosa\n1;2\n")}, follow=True)
    assert "No encuentro las columnas" in r.content.decode() and not Movimiento.objects.exists()
    r = web.post("/bar/pagos/importar/", {}, follow=True)
    assert "No has elegido ningún fichero" in r.content.decode()


def test_las_filas_ilegibles_se_enseñan_no_se_pierden_en_silencio(web):
    r = subir_extracto(web, EXTRACTO + "xx;MAL;1,00;1,00\n")
    html = web.get(r["Location"]).content.decode()
    assert "Línea 10" in html and Movimiento.objects.count() == 8


def test_el_formato_del_banco_se_edita_sin_guardar_la_cuenta_completa(web):
    assert web.post("/bar/pagos/formato/", {**_perfil(), "cuenta_final": "ES76 2100 0168"}).status_code == 200
    r = web.post("/bar/pagos/formato/", {**_perfil(), "cuenta_final": "ABCD"})
    assert r.status_code == 200 and "4 últimas cifras" in r.content.decode()
    assert PerfilImportacion.por_defecto(usuario()).cuenta_final == ""
    assert web.post("/bar/pagos/formato/", {**_perfil(), "cuenta_final": "4820"}).status_code == 302
    html = web.get("/bar/pagos/").content.decode()
    assert "···· 4820" in html and "ES76" not in html


def _perfil():
    return {
        "nombre": "Mi banco", "cuenta_final": "", "separador": "auto", "formato_fecha": "%d/%m/%Y", "sep_miles": ".",
        "sep_decimal": ",", "col_fecha": "Fecha", "col_concepto": "Concepto", "col_concepto_aux": "",
        "col_importe": "Importe", "col_abono": "", "col_saldo": "Saldo",
    }  # fmt: skip


def test_las_pantallas_de_pagos_exigen_sesion(client):
    for url in ("/bar/pagos/", "/bar/pagos/formato/"):
        assert client.get(url, HTTP_HOST="localhost").status_code == 302


def test_una_factura_sin_revisar_se_marca_como_provisional(web):
    factura(estado=Documento.Estado.PROCESADO)
    subir_extracto(web)
    assert "Provisional" in web.get("/bar/pagos/").content.decode()
