# Interfaz móvil primero; Resumen y Revisar con grupos de ejemplo hasta que exista la conciliación

El Bar se diseña para 390 px (y comprueba hasta 360 px): barra inferior Resumen · Subir · Revisar, hoja inferior para el detalle y confirmación de lectura con un toque. Los componentes (`plataforma/static/plataforma/css/movil.css`) usan solo los tokens existentes y no contienen lógica.

La conciliación (emparejar factura con albaranes) todavía no existe, así que Resumen, Revisar y el detalle de grupo muestran **grupos de ejemplo** (`prototipos/bar/ejemplo.py`), marcados «Datos de ejemplo» en pantalla; lo que se haga con ellos no se guarda. Lo real es la subida, la lectura con IA y «Confirmar lectura». Cuando exista la conciliación, `ejemplo.grupos()` se sustituye por los grupos reales con la misma forma.

Dentro de la app móvil las distancias son 24 px entre grupos y 56 px entre secciones (`.app` redefine `--s-group` y `--s-section`); el resto de la plataforma conserva 32 y 88 px.

«Confirmar» solo se ofrece si todo es legible y las cifras cuadran al céntimo; si no, lleva a la ficha completa. Nada se da por bueno sin una persona (regla del sistema).
