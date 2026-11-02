"""Versión móvil: grupos de ejemplo (cifras exactas) y pantallas Resumen, Revisar, Detalle y Confirmar lectura."""

from datetime import date
from decimal import Decimal as D

import pytest

from prototipos.bar import ejemplo
from prototipos.bar.models import Documento
from prototipos.bar.tests.conftest import DATOS_FACTURA
from prototipos.bar.tests.test_flujo import subir

pytestmark = pytest.mark.django_db
HOY = date(2026, 11, 2)


def por_id(slug):
    return next(g for g in ejemplo.grupos(HOY) if g.id == slug)


def test_ferreteria_difiere_en_la_linea_3_por_12_50():
    g = por_id("ferreteria-lleida")
    assert (g.estado, g.diferencia, g.etiqueta) == ("diff", D("12.50"), "+12,50\xa0€")
    assert (g.albaran.total, g.factura.total) == (D("86.40"), D("98.90"))
    assert g.nota == "La factura cobra de más en la línea 3."
    assert g.explicacion == "La factura cobra 2,22\xa0€ por unidad en la línea 3. El albarán indica 1,72\xa0€."
    assert [p.difiere for p in g.pares] == [False, False, True]


def test_un_albaran_sin_factura_esta_pendiente_y_dice_cuantos_dias():
    g = por_id("transportes-garrigues")
    assert (g.estado, g.simbolo, g.etiqueta, g.diferencia) == ("wait", "?", "Falta factura", None)
    assert g.nota == "El albarán llegó hace 9 días."


def test_sin_tolerancia_un_centimo_de_diferencia_ya_no_coincide():
    g = por_id("distribuciones-segre")
    assert (g.estado, g.simbolo) == ("ok", "=")
    peor = ejemplo.GrupoEj(g.id, g.proveedor, g.albaran, g.factura, HOY)
    linea = g.factura.lineas[1]
    cambiada = ejemplo.LineaEj(linea.descripcion, linea.cantidad, linea.precio + D("0.01"), linea.unidad)
    factura = ejemplo.DocEj(g.factura.numero, g.factura.fecha, (g.factura.lineas[0], cambiada))
    assert ejemplo.GrupoEj(peor.id, peor.proveedor, peor.albaran, factura, HOY).estado == "diff"


def test_resumen_y_revisar_ordenan_por_importe_y_suman_lo_por_reclamar():
    lista = ejemplo.grupos(HOY)
    assert [g.estado for g in lista] == ["diff"] * 5 + ["wait"] + ["ok"] * 2
    diffs = ejemplo.con_diferencias(lista)
    assert [g.diferencia for g in diffs] == [D("64.20"), D("22.00"), D("12.50"), D("8.90"), D("3.10")]
    assert ejemplo.resumen(lista) == {"ok": 2, "diff": 5, "wait": 1, "por_reclamar": D("110.70")}


def test_resumen_dice_que_los_grupos_son_de_ejemplo_y_tiene_las_tres_pestanas(web):
    html = web.get("/bar/").content.decode()
    assert "Datos de ejemplo" in html and "Ferretería Lleida" in html and "Todavía no has subido nada" in html
    for destino in ("/bar/", "/bar/subir/", "/bar/revisar/"):
        assert f'href="{destino}"' in html
    assert 'aria-current="page"' in html and "5 diferencias por revisar" in html


def test_revisar_muestra_el_total_por_reclamar_y_el_detalle_de_cada_grupo(web):
    html = web.get("/bar/revisar/").content.decode()
    assert "110,70\xa0€" in html and "+64,20\xa0€" in html and "5 diferencias" in html
    detalle = web.get("/bar/grupos/ferreteria-lleida/").content.decode()
    assert "98,90\xa0€" in detalle and "25 uds. × 2,22\xa0€" in detalle and "Diferencia de 12,50\xa0€" in detalle
    assert web.get("/bar/grupos/no-existe/").status_code == 404


def test_confirmar_lectura_limpia_se_confirma_con_un_toque(web, ia, monkeypatch):
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
