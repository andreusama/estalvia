// Arrastrar y soltar (o elegir) ficheros .csv y .pdf: uno por petición a /subir/. Nada sale de esta máquina.
(function () {
  var form = document.getElementById("subida");
  var zona = document.getElementById("zona");
  var entrada = document.getElementById("ficheros");
  var estado = document.getElementById("estado-subida");
  var lista = document.getElementById("problemas-subida");
  var token = form.querySelector("input[name=csrfmiddlewaretoken]").value;

  function enviar(fichero) {
    var datos = new FormData();
    datos.append("fichero", fichero);
    return fetch("/subir/", { method: "POST", body: datos, headers: { "X-CSRFToken": token }, credentials: "same-origin" })
      .then(function (r) { return r.json().catch(function () { return { ok: false, mensaje: "Respuesta no válida del servidor." }; }); })
      .catch(function () { return { ok: false, mensaje: "No se pudo contactar con el servidor." }; });
  }

  async function subir(ficheros) {
    lista.textContent = "";
    var todoBien = true;
    for (var i = 0; i < ficheros.length; i++) {
      estado.textContent = "Subiendo " + (i + 1) + " de " + ficheros.length + "…";
      var r = await enviar(ficheros[i]);
      estado.textContent = r.mensaje;
      todoBien = todoBien && r.ok;
      (r.problemas || []).forEach(function (p) {
        var li = document.createElement("li");
        li.textContent = p;  // textContent: el texto del servidor nunca se interpreta como HTML
        lista.appendChild(li);
      });
      if (!r.ok) break;
    }
    if (todoBien) window.location.reload();
  }

  ["dragenter", "dragover"].forEach(function (n) {
    zona.addEventListener(n, function (e) { e.preventDefault(); zona.classList.add("sobre"); });
  });
  ["dragleave", "drop"].forEach(function (n) {
    zona.addEventListener(n, function (e) { e.preventDefault(); zona.classList.remove("sobre"); });
  });
  zona.addEventListener("drop", function (e) { subir(Array.from(e.dataTransfer.files)); });
  entrada.addEventListener("change", function () { subir(Array.from(entrada.files)); });
})();
