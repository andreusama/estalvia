// Sube los archivos de uno en uno (Vercel limita el cuerpo a 4,5 MB) y reduce las fotos antes de enviarlas.
(function () {
  var form = document.getElementById('form-subir');
  if (!form) return;
  var input = document.getElementById('archivo');
  var lista = document.getElementById('estado-subida');
  var boton = form.querySelector('button[type=submit]');
  var maxBytes = (parseInt(form.dataset.maxMb, 10) || 4) * 1024 * 1024;
  var LADO = 2200, CALIDAD = 0.88;

  function linea(texto, ok) {
    var li = document.createElement('li');
    li.textContent = texto;
    if (ok === false) li.className = 'doubt';
    lista.appendChild(li);
    return li;
  }

  function reducir(archivo) {
    if (!/^image\/(jpeg|png|webp)$/.test(archivo.type) || !window.createImageBitmap) return Promise.resolve(archivo);
    return createImageBitmap(archivo, { imageOrientation: 'from-image' }).then(function (img) {
      var escala = Math.min(1, LADO / Math.max(img.width, img.height));
      if (escala === 1 && archivo.size < maxBytes * 0.6) return archivo;
      var c = document.createElement('canvas');
      c.width = Math.round(img.width * escala);
      c.height = Math.round(img.height * escala);
      c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
      return new Promise(function (res) {
        c.toBlob(function (b) { res(b || archivo); }, 'image/jpeg', CALIDAD);
      });
    }).catch(function () { return archivo; });
  }

  form.addEventListener('submit', function (e) {
    var archivos = Array.prototype.slice.call(input.files);
    if (!archivos.length || !window.fetch) return; // sin JS moderno, envío normal
    e.preventDefault();
    boton.disabled = true;
    lista.innerHTML = '';
    var token = form.querySelector('[name=csrfmiddlewaretoken]').value;
    var urls = [], fallos = 0;

    archivos.reduce(function (previa, archivo, i) {
      return previa.then(function () {
        var li = linea('Subiendo ' + (i + 1) + ' de ' + archivos.length + ': ' + archivo.name + '…');
        return reducir(archivo).then(function (blob) {
          if (blob.size > maxBytes) throw new Error('pesa demasiado, incluso reducido');
          var fd = new FormData();
          var nombre = blob === archivo ? archivo.name : archivo.name.replace(/\.[^.]+$/, '') + '.jpg';
          fd.append('archivo', blob, nombre);
          fd.append('csrfmiddlewaretoken', token);
          return fetch(form.action, { method: 'POST', body: fd, headers: { 'X-Requested-With': 'fetch' }, credentials: 'same-origin' });
        }).then(function (r) {
          return r.json().catch(function () { throw new Error('el servidor no pudo recibirlo (' + r.status + ')'); });
        }).then(function (j) {
          if (!j.ok) throw new Error(j.error);
          li.textContent = '= ' + archivo.name + (j.nuevo ? '' : ' (ya estaba subido)');
          urls.push(j.url);
        }).catch(function (err) {
          fallos++;
          li.textContent = '≠ ' + archivo.name + ': ' + err.message;
          li.className = 'doubt';
        });
      });
    }, Promise.resolve()).then(function () {
      if (!fallos) {
        window.location.href = urls.length === 1 ? urls[0] : form.dataset.inicio || window.location.pathname.replace(/subir\/$/, '');
      } else {
        boton.disabled = false;
      }
    });
  });
})();
