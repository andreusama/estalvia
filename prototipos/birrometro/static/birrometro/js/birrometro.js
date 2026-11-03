// Birròmetro: al mover un deslizador o cambiar un dato se pide el resultado al servidor (la cuenta la hace él).
(function () {
  var form = document.getElementById("birrometro");
  if (!form) return;
  var salida = document.getElementById("resultado");
  var espera = null, peticion = 0;

  function mostrar() { // solo repite lo que has escrito, con coma; no calcula nada
    form.querySelectorAll("output[data-de]").forEach(function (o) {
      var campo = document.getElementById(o.getAttribute("data-de"));
      if (campo) o.textContent = Number(campo.value).toFixed(2).replace(".", ",");
    });
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
  pedir();
})();
