// Lanza la lectura con la IA nada más abrir un documento recién subido (una petición por documento)
// y, al terminar, abre «Confirmar lectura» (o la ficha, si hubo un error).
(function () {
  var form = document.getElementById('form-leer');
  if (!form || !form.dataset.autoleer || !window.fetch) return;
  var boton = form.querySelector('button');
  boton.disabled = true;
  fetch(form.action, {
    method: 'POST', credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' },
    body: new FormData(form)
  }).then(function (r) { return r.json(); })
    .then(function (j) { window.location.href = j.url; })
    .catch(function () { window.location.reload(); });
})();
