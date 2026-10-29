(function () {
  const datos = JSON.parse(document.getElementById("datos-informe").textContent);
  const color = { "Potencia contratada": "#1a5fb4", "Energía consumida": "#e5a50a", "Otros costes fijos": "#613583", "Impuestos": "#5e5c64" };
  const nivel = { cara: "#c01c28", normal: "#e5a50a", barata: "#26a269" };
  new Chart(document.getElementById("grafico-reparto"), {
    type: "doughnut",
    data: { labels: datos.reparto.nombres,
            datasets: [{ data: datos.reparto.importes, backgroundColor: datos.reparto.nombres.map((n) => color[n]) }] },
    options: { animation: false, maintainAspectRatio: false, plugins: { legend: { display: false } } },
  });
  new Chart(document.getElementById("grafico-franjas"), {
    type: "bar",
    data: { labels: datos.franjas.nombres,
            datasets: [{ data: datos.franjas.costes, backgroundColor: datos.franjas.niveles.map((n) => nivel[n]) }] },
    options: { animation: false, maintainAspectRatio: false, plugins: { legend: { display: false } },
               scales: { y: { beginAtZero: true, title: { display: true, text: "€ de energía" } } } },
  });
})();
