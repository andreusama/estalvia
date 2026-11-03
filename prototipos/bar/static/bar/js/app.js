// Comportamiento de la versión móvil del Bar: aviso breve sobre la barra de pestañas y vibración ligera.
(function () {
  var aviso = document.getElementById('aviso'), temporizador;
  function avisar(texto) {
    if (!aviso) return;
    aviso.textContent = texto;
    aviso.classList.add('is-visible');
    clearTimeout(temporizador);
    temporizador = setTimeout(function () { aviso.classList.remove('is-visible'); }, 3200);
    if (navigator.vibrate) navigator.vibrate(15);
  }
  // Una confirmación que llega con la página (documento confirmado, pago confirmado...) se enseña como aviso breve.
  var inicial = document.querySelector('[data-aviso]');
  if (inicial) { avisar(inicial.dataset.aviso); inicial.hidden = true; }
})();
