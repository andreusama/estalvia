// Birròmetro: al mover el deslizador o cambiar un dato se pide el resultado al servidor (la cuenta la hace él).
(function () {
  var form = document.getElementById("birrometro");
  if (!form) return;
  var salida = document.getElementById("resultado");
  var texto = document.getElementById("precio-venta-texto");
  var deslizador = document.getElementById("id_precio_venta");
  var espera = null, peticion = 0;

  function mostrar() { // solo repite lo que has escrito, con coma; no calcula nada
    texto.textContent = Number(deslizador.value).toFixed(2).replace(".", ",");
  }

  function pedir() {
    if (!form.litros.value || !form.precio.value) return; // sin litros ni precio no hay nada que calcular
    var datos = new URLSearchParams(new FormData(form));
    datos.delete("csrfmiddlewaretoken");
    var numero = ++peticion;
    fetch(form.action + "?" + datos.toString(), { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (html) { if (html !== null && numero === peticion) salida.innerHTML = html; })
      .catch(function () {});
  }

  function cambio() { mostrar(); clearTimeout(espera); espera = setTimeout(pedir, 150); }

  mostrar();
  form.addEventListener("input", cambio);
  form.addEventListener("change", cambio);
  document.getElementById("calcular").hidden = true; // con JavaScript se calcula solo
  if (form.litros && form.litros.value && form.precio.value) pedir();
})();
