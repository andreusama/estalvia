---
status: grupos de ejemplo retirados; ver más abajo
---

# Interfaz móvil primero

El Bar se diseña para 390 px (y comprueba hasta 360 px): barra inferior Resumen · Subir · Revisar, subida con galería, cámara y PDF, y confirmación de lectura con un toque. Los componentes (`plataforma/static/plataforma/css/movil.css`) usan solo los tokens existentes y no contienen lógica.

Dentro de la app móvil las distancias son 24 px entre grupos y 56 px entre secciones (`.app` redefine `--s-group` y `--s-section`); el resto de la plataforma conserva 32 y 88 px.

«Confirmar» solo se ofrece si todo es legible y las cifras cuadran al céntimo; si no, lleva a la ficha completa. Nada se da por bueno sin una persona (regla del sistema).

## Actualización: sin datos de ejemplo

La primera versión mostraba grupos de albarán y factura inventados (la conciliación aún no existía). Se retiraron: ninguna pantalla enseña datos que no sean del usuario. Resumen cuenta facturas pagadas, documentos por revisar y facturas sin pagar; Revisar lista los documentos que esperan revisión y los avisos de pagos; el contador rojo de la barra suma esas dos cosas. La hoja de detalle y las filas deslizables se quitaron con ellos y volverán cuando exista la conciliación de albaranes con facturas.
