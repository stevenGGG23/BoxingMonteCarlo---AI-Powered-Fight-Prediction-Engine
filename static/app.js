async function fetchFighters() {
  const res = await fetch('/api/fighters');
  const data = await res.json();
  return data.fighters || [];
}

function populateSelect(id, fighters, selected) {
  const sel = document.getElementById(id);
  sel.innerHTML = '';
  fighters.forEach(f => {
    const opt = document.createElement('option');
    opt.value = f;
    opt.textContent = f;
    if (f === selected) opt.selected = true;
    sel.appendChild(opt);
  });
}

let chart = null;

function renderChart(labels, values) {
  const ctx = document.getElementById('resultChart').getContext('2d');
  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Wins',
        data: values,
        backgroundColor: ['#1f77b4','#ff7f0e','#2ca02c']
      }]
    },
    options: {
      responsive: true,
      plugins: {legend:{display:false}}
    }
  });
}

function showStatus(msg) { document.getElementById('status').textContent = msg; }

function showStats(f1, f2, results) {
  const s = document.getElementById('stats');
  s.innerHTML = `
    <strong>${f1.name}</strong>: ${results.results.fighter1_wins.toLocaleString()} wins (${results.results.fighter1_win_pct.toFixed(2)}%)<br>
    <strong>${f2.name}</strong>: ${results.results.fighter2_wins.toLocaleString()} wins (${results.results.fighter2_win_pct.toFixed(2)}%)<br>
    <strong>Draws</strong>: ${results.results.draws.toLocaleString()} (${results.results.draw_pct.toFixed(2)}%)<br>
    <hr>
    <strong>Execution Time</strong>: ${results.results.execution_time.toFixed(2)}s<br>
    <strong>Throughput</strong>: ${Math.round(results.results.throughput).toLocaleString()} sims/s
  `;
}

window.addEventListener('DOMContentLoaded', async () => {
  const fighters = await fetchFighters();
  populateSelect('fighter1', fighters, fighters[0]);
  populateSelect('fighter2', fighters, fighters[1] || fighters[0]);

  const form = document.getElementById('sim-form');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    showStatus('Running simulation — this may take a few seconds...');
    const f1 = document.getElementById('fighter1').value;
    const f2 = document.getElementById('fighter2').value;
    const n = parseInt(document.getElementById('n_simulations').value || '10000', 10);
    const use_mp = document.getElementById('use_mp').checked;

    try {
      const res = await fetch('/api/simulate', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({fighter1: f1, fighter2: f2, n_simulations: n, use_multiprocessing: use_mp})
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      showStatus('Simulation complete.');
      renderChart([f1, f2, 'Draws'], [data.results.fighter1_wins, data.results.fighter2_wins, data.results.draws]);
      showStats(data.fighter1, data.fighter2, data);
    } catch (err) {
      showStatus('Error: ' + err.message);
    }
  });
});
