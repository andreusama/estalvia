(function () {
  const datos = JSON.parse(document.getElementById("datos-curva").textContent);
  new Chart(document.getElementById("curva"), {
    type: "line",
    data: {
      labels: datos.horas.map((h) => h + ":00"),
      datasets: [
        { label: "Laborables", data: datos.laborable, borderColor: "#1a5fb4", spanGaps: false },
        { label: "Fines de semana", data: datos.finde, borderColor: "#e66100", spanGaps: false },
      ],
    },
    options: { animation: false, scales: { y: { beginAtZero: true, title: { display: true, text: "kWh" } } } },
  });
})();
