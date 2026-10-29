(function () {
  const datos = JSON.parse(document.getElementById("datos-informe").textContent);
  const color = { "Potencia contratada": "#1a5fb4", "Energía consumida": "#e5a50a", "Bono social": "#a51d6a", "Alquiler del contador": "#613583", "Impuestos": "#5e5c64" };
  const nivel = { cara: "#c01c28", normal: "#e5a50a", barata: "#26a269" };
  new Chart(document.getElementById("grafico-reparto"), {
    type: "doughnut",
    data: { labels: datos.reparto.nombres,
            datasets: [{ data: datos.reparto.importes, backgroundColor: datos.reparto.nombres.map((n) => color[n]) }] },
    options: { animation: false, maintainAspectRatio: false, plugins: { legend: { display: false } } },
  });
  new Chart(document.getElementById("grafico-periodos"), {
    type: "bar",
    data: { labels: datos.periodos.nombres,
            datasets: [{ data: datos.periodos.costes, backgroundColor: datos.periodos.niveles.map((n) => nivel[n]) }] },
    options: { animation: false, maintainAspectRatio: false, plugins: { legend: { display: false } },
               scales: { y: { beginAtZero: true, title: { display: true, text: "€ de energía" } } } },
  });
  new Chart(document.getElementById("grafico-perfil"), {
    type: "line",
    data: { labels: Array.from({ length: 24 }, (_, h) => h + ":00"),
            datasets: [
              { label: "Laborables", data: datos.perfil.laborable, borderColor: "#1a5fb4", spanGaps: false },
              { label: "Fines de semana y festivos", data: datos.perfil.finde, borderColor: "#e66100", spanGaps: false },
            ] },
    options: { animation: false, maintainAspectRatio: false,
               scales: { y: { beginAtZero: true, title: { display: true, text: "kWh por hora" } } } },
  });
})();
