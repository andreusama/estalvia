// Comportamiento de la versión móvil del Bar: avisos breves, hoja inferior de detalle y filas que se deslizan.
// Los grupos de las pantallas Resumen y Revisar son de ejemplo: marcar o reclamar no se guarda en ninguna parte.
(function () {
  var reducido = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---- Aviso breve sobre la barra de pestañas (y vibración ligera si el dispositivo lo permite)
  var aviso = document.getElementById('aviso'), temporizador;
  function avisar(texto, vibrar) {
    if (!aviso) return;
    aviso.textContent = texto;
    aviso.classList.add('is-visible');
    clearTimeout(temporizador);
    temporizador = setTimeout(function () { aviso.classList.remove('is-visible'); }, 3200);
    if (vibrar && navigator.vibrate) navigator.vibrate(15);
  }
  var inicial = document.querySelector('[data-aviso]');
  if (inicial) { avisar(inicial.dataset.aviso, true); inicial.hidden = true; }

  // ---- Revisar: contadores y total tras marcar un grupo
  function euros(centimos) {
    return new Intl.NumberFormat('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2, useGrouping: 'always' })
      .format(centimos / 100) + ' €';
  }
  function actualizar() {
    var filas = document.querySelectorAll('[data-fila]');
    var n = filas.length, total = 0;
    filas.forEach(function (f) { total += parseInt(f.dataset.centimos, 10) || 0; });
    var el;
    if ((el = document.getElementById('rev-n'))) el.textContent = n;
    if ((el = document.getElementById('rev-n-txt'))) el.textContent = n === 1 ? el.dataset.uno : el.dataset.varios;
    if ((el = document.getElementById('rev-total'))) el.textContent = euros(total);
    if ((el = document.getElementById('tab-contador'))) { el.textContent = n; el.hidden = n === 0; }
    var vacio = document.getElementById('rev-vacio'), contenido = document.getElementById('rev-contenido');
    if (vacio && contenido) { vacio.hidden = n !== 0; contenido.hidden = n === 0; }
  }
  function marcarRevisado(id) {
    var fila = document.querySelector('[data-fila="' + id + '"]');
    if (fila) { fila.remove(); actualizar(); }
    avisar('Marcado como revisado (ejemplo: no se guarda).', true);
  }

  // ---- Hoja inferior de detalle
  var hoja = document.getElementById('hoja');
  if (hoja && typeof hoja.showModal === 'function') {
    var cuerpo = document.getElementById('hoja-cuerpo'), pie = document.getElementById('hoja-pie');
    var asa = hoja.querySelector('[data-asa]');

    document.addEventListener('click', function (e) {
      var enlace = e.target.closest('a[data-grupo]');
      if (!enlace || e.defaultPrevented) return;
      var plantilla = document.getElementById('d-' + enlace.dataset.grupo);
      if (!plantilla) return;
      e.preventDefault();
      cuerpo.replaceChildren(plantilla.content.cloneNode(true));
      var detalle = cuerpo.firstElementChild;
      hoja.dataset.id = detalle.dataset.id;
      pie.hidden = detalle.dataset.estado !== 'diff';
      cuerpo.scrollTop = 0;
      hoja.style.transform = '';
      hoja.showModal();
    });

    hoja.addEventListener('click', function (e) {
      if (e.target === hoja || e.target.closest('[data-cerrar]')) { hoja.close(); return; }
      var accion = e.target.closest('[data-accion]');
      if (!accion) return;
      var id = hoja.dataset.id;
      hoja.close();
      if (accion.dataset.accion === 'revisado') marcarRevisado(id);
      else avisar('Reclamar al proveedor todavía no está disponible (ejemplo).');
    });

    // Arrastrar el asa hacia abajo para cerrar
    var y0 = null;
    asa.addEventListener('pointerdown', function (e) { y0 = e.clientY; asa.setPointerCapture(e.pointerId); });
    asa.addEventListener('pointermove', function (e) {
      if (y0 === null) return;
      hoja.style.transform = 'translateY(' + Math.max(0, e.clientY - y0) + 'px)';
    });
    function soltar(e) {
      if (y0 === null) return;
      var dy = e.clientY - y0;
      y0 = null;
      hoja.style.transform = '';
      if (dy > 120) hoja.close();
    }
    asa.addEventListener('pointerup', soltar);
    asa.addEventListener('pointercancel', soltar);
  }

  // ---- Revisar: deslizar a la izquierda para marcar como revisado
  document.querySelectorAll('.desliza').forEach(function (fila) {
    var fg = fila.querySelector('.desliza__fg');
    var x0 = null, dx = 0, arrastrando = false;
    fila.addEventListener('pointerdown', function (e) {
      if (e.pointerType === 'mouse' && e.button !== 0) return;
      x0 = e.clientX; dx = 0; arrastrando = false;
      fg.classList.remove('suelta');
    });
    fila.addEventListener('pointermove', function (e) {
      if (x0 === null) return;
      dx = Math.min(0, e.clientX - x0);
      if (!arrastrando && Math.abs(dx) > 8) { arrastrando = true; fila.setPointerCapture(e.pointerId); }
      if (arrastrando) fg.style.transform = 'translateX(' + dx + 'px)';
    });
    function terminar() {
      if (x0 === null) return;
      x0 = null;
      fg.classList.add('suelta');
      if (arrastrando && dx < -96) {
        fg.style.transform = 'translateX(-100%)';
        setTimeout(function () { marcarRevisado(fila.dataset.fila); }, reducido ? 0 : 200);
      } else {
        fg.style.transform = '';
      }
    }
    fila.addEventListener('pointerup', terminar);
    fila.addEventListener('pointercancel', terminar);
    // Un arrastre no es un toque: no abre el detalle
    fila.addEventListener('click', function (e) { if (arrastrando) { e.preventDefault(); e.stopPropagation(); arrastrando = false; } }, true);
  });
})();
