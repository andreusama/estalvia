// Lanza la lectura con la IA nada más abrir un documento recién subido (una petición por documento).
(function () {
  var form = document.getElementById('form-leer');
  if (!form || !form.dataset.autoleer || !window.fetch) return;
  var boton = form.querySelector('button');
  boton.disabled = true;
  fetch(form.action, {
    method: 'POST', credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' },
    body: new FormData(form)
  }).then(function () { window.location.reload(); })
    .catch(function () { boton.disabled = false; });
})();
