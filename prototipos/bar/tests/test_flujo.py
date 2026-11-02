"""Subir, leer con la IA (falsa) y revisar: el flujo completo sin llamar a la API real."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from prototipos.bar.models import Documento, Evento, Proveedor
from prototipos.bar.tests.conftest import DATOS_FACTURA, PNG

pytestmark = pytest.mark.django_db


def subir(web, contenido=PNG, nombre="foto.png", tipo="image/png", ajax=True):
    f = SimpleUploadedFile(nombre, contenido, content_type=tipo)
    return web.post("/bar/subir/", {"archivo": f}, headers={"X-Requested-With": "fetch"} if ajax else {})


def test_subir_guarda_el_original_por_leer(web):
    r = subir(web)
    assert r.status_code == 200 and r.json()["ok"]
    d = Documento.objects.get()
    assert (
        d.estado == Documento.Estado.PENDIENTE and bytes(d.archivo) == PNG and d.eventos.filter(tipo="subido").exists()
    )


def test_archivo_repetido_no_se_guarda_dos_veces(web):
    subir(web)
    r = subir(web)
    assert r.json()["nuevo"] is False and Documento.objects.count() == 1


@pytest.mark.parametrize(
    "contenido,tipo", [(b"%PDF", "text/plain"), (b"", "image/png"), (b"x" * (4 * 1024 * 1024 + 1), "image/png")]
)
def test_archivos_no_validos_se_rechazan(web, contenido, tipo):
    r = subir(web, contenido=contenido, tipo=tipo)
    assert r.status_code == 400 and not r.json()["ok"] and Documento.objects.count() == 0


def test_subida_sin_javascript_redirige_al_documento(web):
    r = subir(web, ajax=False)
    assert r.status_code == 302 and r["Location"] == f"/bar/documentos/{Documento.objects.get().pk}/"


def test_leer_rellena_los_datos_y_marca_lo_dudoso(web, ia):
    cliente = ia(DATOS_FACTURA)
    subir(web)
    d = Documento.objects.get()
    r = web.post(f"/bar/documentos/{d.pk}/leer/", headers={"X-Requested-With": "fetch"})
    d.refresh_from_db()
    assert r.json()["estado"] == "procesado" and d.estado == Documento.Estado.PROCESADO
    assert (d.tipo, d.numero, str(d.total), d.proveedor_nif) == ("factura", "F26-00001", "12.69", "B00000000")
    assert d.lineas.count() == 1 and d.desglose_iva.count() == 1
    assert d.referencias.get().numero_normalizado == "A00001"
    assert d.campos_dudosos[0]["campo"] == "numero" and d.respuesta_ia["numero"] == "F26-00001"
    llamada = cliente.llamadas[0]
    assert llamada["model"] == "claude-sonnet-5-5" and "tool_choice" not in llamada
    assert llamada["output_config"]["format"]["type"] == "json_schema"


def test_error_de_la_ia_deja_el_documento_en_error_y_se_puede_reintentar(web, ia):
    ia(error=RuntimeError("red caída"))
    subir(web)
    d = Documento.objects.get()
    web.post(f"/bar/documentos/{d.pk}/leer/")
    d.refresh_from_db()
    assert (
        d.estado == Documento.Estado.ERROR
        and "No se pudo contactar" in d.error_texto
        and "red caída" not in d.error_texto
    )
    ia(DATOS_FACTURA)
    web.post(f"/bar/documentos/{d.pk}/leer/")
    d.refresh_from_db()
    assert d.estado == Documento.Estado.PROCESADO and d.error_texto == ""


def leido(web, ia):
    ia(DATOS_FACTURA)
    subir(web)
    d = Documento.objects.get()
    web.post(f"/bar/documentos/{d.pk}/leer/")
    return d


def formulario(web, d, **cambios):
    """Reenvía el formulario de revisión tal como lo ve el usuario, con los cambios indicados."""
    html = web.get(f"/bar/documentos/{d.pk}/").content.decode()
    import re

    datos = {}
    for m in re.finditer(r'<input[^>]*name="([^"]+)"[^>]*>', html):
        etiqueta, nombre = m.group(0), m.group(1)
        if 'type="checkbox"' in etiqueta or nombre == "csrfmiddlewaretoken":
            continue
        v = re.search(r'value="([^"]*)"', etiqueta)
        datos[nombre] = v.group(1) if v else ""
    datos["tipo"] = d.tipo
    datos.update(cambios)
    return datos


def test_revisar_corrige_guarda_la_historia_y_vincula_proveedor(web, ia):
    d = leido(web, ia)
    html = web.get(f"/bar/documentos/{d.pk}/").content.decode()
    assert "último dígito borroso" in html and "Se ve el borde de otra hoja" in html and "Las cifras cuadran" in html
    datos = formulario(web, d, numero="F26-00002", total="12,70", accion="revisar")
    r = web.post(f"/bar/documentos/{d.pk}/", datos)
    assert r.status_code == 302 and "revisado=1" in r["Location"]
    d.refresh_from_db()
    assert d.estado == Documento.Estado.REVISADO and d.numero == "F26-00002" and str(d.total) == "12.70"
    assert d.proveedor == Proveedor.objects.get(nif="B00000000") and d.revisado_en
    assert d.respuesta_ia["total"] == "12.69"  # lo que dijo la IA no se toca
    detalles = " ".join(Evento.objects.filter(documento=d, tipo="corregido").values_list("detalle", flat=True))
    assert "numero" in detalles and "F26-00002" in detalles and "total" in detalles
    assert "No cuadra" in web.get(f"/bar/documentos/{d.pk}/").content.decode()  # 10,49 + 2,20 ≠ 12,70


def test_importe_ilegible_no_se_guarda(web, ia):
    d = leido(web, ia)
    r = web.post(f"/bar/documentos/{d.pk}/", formulario(web, d, total="doce", accion="guardar"))
    assert r.status_code == 200 and "Escribe un número" in r.content.decode()
    d.refresh_from_db()
    assert str(d.total) == "12.69"


def test_documento_sin_base_de_datos_avisa(web, settings):
    settings.DATABASES = {}
    r = web.get("/bar/")
    assert r.status_code == 503 and "DATABASE_URL" in r.content.decode()


def test_lista_agrupa_por_estado(web, ia):
    leido(web, ia)
    html = web.get("/bar/").content.decode()
    assert "Por revisar" in html and "Distribuciones Ejemplo S.L." in html and "12,69" in html


def test_el_archivo_original_solo_se_sirve_con_sesion(web, client):
    subir(web)
    d = Documento.objects.get()
    assert web.get(f"/bar/documentos/{d.pk}/archivo/").content == PNG
    assert client.get(f"/bar/documentos/{d.pk}/archivo/", HTTP_HOST="localhost").status_code == 302
