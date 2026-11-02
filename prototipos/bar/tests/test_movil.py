"""Versión móvil: Resumen, Revisar, contador de la barra inferior y Confirmar lectura, solo con datos reales."""

from decimal import Decimal as D

import pytest

from prototipos.bar import panel
from prototipos.bar.models import Documento
from prototipos.bar.tests.conftest import DATOS_FACTURA
from prototipos.bar.tests.test_flujo import leido, subir
from prototipos.bar.tests.test_pagos import factura, importar

pytestmark = pytest.mark.django_db


def test_sin_datos_no_se_inventa_nada(web):
    resumen = web.get("/bar/").content.decode()
    assert "Todavía no has subido nada" in resumen and "ejemplo" not in resumen.lower()
    assert "summary__bar" not in resumen  # sin facturas no hay barra de proporción
    revisar = web.get("/bar/revisar/").content.decode()
    assert "Todo en orden este mes" in revisar and "ejemplo" not in revisar.lower()
    assert 'id="tab-contador"' in revisar and "hidden" in revisar.split('id="tab-contador"')[1][:80]  # contador oculto
    assert panel.cifras()["contador"] == 0


def test_resumen_cuenta_pagadas_por_revisar_y_sin_pagar_con_datos_reales(web):
    pagada = factura(numero="F26-00001", total="12.69")
    factura(numero="F26-00002", total="40.00")
    factura(numero="F26-00003", total="55.00", estado=Documento.Estado.PROCESADO)
    from prototipos.bar import pagos

    pagos.pagar_en_efectivo(pagada)
    c = panel.cifras()
    assert (c["pagadas"], c["por_revisar"], c["sin_pagar"]) == (1, 1, 2)
    html = web.get("/bar/").content.decode()
    assert "Pagadas" in html and "Por revisar" in html and "Sin pagar" in html and "summary__bar" in html


def test_revisar_lista_lo_que_necesita_una_accion_y_el_contador_lo_cuenta(web, ia):
    d = leido(web, ia)  # sube y lee: queda «por revisar»
    factura(numero="F26-00009", total="12.69")
    importar(
        "Fecha;Concepto;Importe;Saldo\n"
        "28/10/2026;TRANSF A DISTRIBUCIONES EJEMPLO SL FRA F26-00009;-12,69;1,00\n"
        "28/10/2026;TRANSF A DISTRIBUCIONES EJEMPLO SL FRA F26-00009;-12,69;2,00\n"
    )
    c = panel.cifras()
    assert [x.pk for x in c["docs"]] == [d.pk] and len(c["avisos"]) == 1 and c["contador"] == 2
    html = web.get("/bar/revisar/").content.decode()
    assert "2 cosas por revisar" in html and "Posible cobro doble" in html and "Por revisar" in html
    assert 'class="tab__badge"' in html and "datos de ejemplo" not in html.lower()


def test_los_documentos_que_no_cuadran_van_primero_en_revisar(web, ia):
    ia({**DATOS_FACTURA, "total": "99.99", "campos_dudosos": []})  # el total no es base más IVA: no cuadra
    subir(web)
    mal = Documento.objects.get()
    web.post(f"/bar/documentos/{mal.pk}/leer/")
    ok = factura(numero="F26-00007", total="500.00", estado=Documento.Estado.PROCESADO)
    orden = [d.pk for d in panel.documentos_por_revisar()]
    assert orden == [mal.pk, ok.pk] and panel.documentos_por_revisar()[0].fallos
    assert "No cuadra" in web.get("/bar/revisar/").content.decode()


def test_confirmar_lectura_limpia_se_confirma_con_un_toque(web, ia):
    ia({**DATOS_FACTURA, "campos_dudosos": []})
    subir(web)
    d = Documento.objects.get()
    r = web.post(f"/bar/documentos/{d.pk}/leer/", headers={"X-Requested-With": "fetch"})
    assert r.json()["url"] == f"/bar/documentos/{d.pk}/confirmar/"
    html = web.get(r.json()["url"]).content.decode()
    assert "Todo legible" in html and "12,69\xa0€" in html and "Distribuciones Ejemplo S.L." in html
    r = web.post(f"/bar/documentos/{d.pk}/confirmar/")
    d.refresh_from_db()
    assert r.status_code == 302 and d.estado == Documento.Estado.REVISADO
    assert d.eventos.filter(tipo="revisado").exists()
    assert D(d.total) == D("12.69")
    assert "Documento confirmado" in web.get("/bar/?confirmado=1").content.decode()


def test_confirmar_lectura_con_dudas_no_se_puede_dar_por_buena_aqui(web, ia):
    ia(DATOS_FACTURA)  # trae un campo dudoso
    subir(web)
    d = Documento.objects.get()
    web.post(f"/bar/documentos/{d.pk}/leer/")
    html = web.get(f"/bar/documentos/{d.pk}/confirmar/").content.decode()
    assert "Revisa los datos" in html and "Revisar y corregir" in html and "Confirmar</button>" not in html
    web.post(f"/bar/documentos/{d.pk}/confirmar/")
    d.refresh_from_db()
    assert d.estado == Documento.Estado.PROCESADO  # nada se da por bueno sin que una persona lo revise
