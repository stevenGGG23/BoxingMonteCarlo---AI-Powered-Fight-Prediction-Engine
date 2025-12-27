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
        backgroundColor: ['#e53e3e','#2b6cb0','#48bb78']
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
  // Build a union of keys to show in table, in preferred order
  const preferred = ['name','wins','losses','draws','total_bouts','ko_wins','win_rate','ko_rate','height','reach','weight','source'];
  const keys = new Set([...Object.keys(f1), ...Object.keys(f2), ...preferred]);
  const ordered = [...preferred, ...Array.from(keys).filter(k => !preferred.includes(k))];

  // Build table
  const table = document.createElement('table');
  table.className = 'stats-table';
  const thead = document.createElement('thead');
  const hrow = document.createElement('tr');
  ['Field', f1.name || 'Fighter 1', f2.name || 'Fighter 2'].forEach(t => {
    const th = document.createElement('th'); th.textContent = t; hrow.appendChild(th);
  });
  thead.appendChild(hrow);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  ordered.forEach(key => {
    if (!key) return;
    const row = document.createElement('tr');
    const label = document.createElement('td');
    label.textContent = key.replace(/_/g,' ');
    row.appendChild(label);
    const v1 = document.createElement('td');
    const v2 = document.createElement('td');
    let val1 = f1[key];
    let val2 = f2[key];
    // Special computed fields
    if (key === 'win_rate') val1 = (f1.wins && f1.total_bouts) ? (f1.wins / f1.total_bouts).toFixed(3) : '';
    if (key === 'win_rate') val2 = (f2.wins && f2.total_bouts) ? (f2.wins / f2.total_bouts).toFixed(3) : '';
    if (key === 'ko_rate') val1 = (f1.ko_wins && f1.total_bouts) ? (f1.ko_wins / f1.total_bouts).toFixed(3) : '';
    if (key === 'ko_rate') val2 = (f2.ko_wins && f2.total_bouts) ? (f2.ko_wins / f2.total_bouts).toFixed(3) : '';
    v1.textContent = (val1 === undefined || val1 === null) ? '' : String(val1);
    v2.textContent = (val2 === undefined || val2 === null) ? '' : String(val2);
    row.appendChild(v1);
    row.appendChild(v2);
    tbody.appendChild(row);
  });
  table.appendChild(tbody);

  // Summary and download button
  const summary = document.createElement('div');
  summary.className = 'stats-summary';
  summary.innerHTML = `<strong>Results:</strong> ${results.results.fighter1_win_pct.toFixed(2)}% / ${results.results.fighter2_win_pct.toFixed(2)}% (Draws: ${results.results.draw_pct.toFixed(2)}%)`;
  s.innerHTML = '';
  s.appendChild(summary);
  s.appendChild(table);
  // CSV download removed per user request
}

function tableToCSV(table) {
  const rows = Array.from(table.querySelectorAll('tr'));
  return rows.map(r => Array.from(r.querySelectorAll('th,td')).map(c => '"' + c.textContent.replace(/"/g,'""') + '"').join(',')).join('\n');
}
window.addEventListener('DOMContentLoaded', async () => {
  const fighters = await fetchFighters();
  populateSelect('fighter1', fighters, fighters[0]);
  populateSelect('fighter2', fighters, fighters[1] || fighters[0]);

  // Ensure custom input fields exist (added in template)
  const f1Custom = document.getElementById('fighter1_custom');
  const f2Custom = document.getElementById('fighter2_custom');

  const form = document.getElementById('sim-form');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    showStatus('Running simulation — this may take a few seconds...');
    // Prefer custom input if provided, otherwise use the select
    const f1_select_val = document.getElementById('fighter1').value;
    const f2_select_val = document.getElementById('fighter2').value;
    const f1_custom_val = f1Custom ? f1Custom.value.trim() : '';
    const f2_custom_val = f2Custom ? f2Custom.value.trim() : '';

    const f1 = f1_custom_val || f1_select_val;
    const f2 = f2_custom_val || f2_select_val;
    const n = parseInt(document.getElementById('n_simulations').value || '10000', 10);
    // Multiprocessing is enabled by default on the server
    const use_mp = true;

    try {
      const res = await fetch('/api/simulate', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({fighter1: f1, fighter2: f2, n_simulations: n, use_multiprocessing: use_mp})
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      let statusMsg = 'Simulation complete.';
      if (data.warnings && data.warnings.length) {
        statusMsg += ' \u2014 Warnings: ' + data.warnings.join(' ');
      }
      showStatus(statusMsg);
      renderChart([f1, f2, 'Draws'], [data.results.fighter1_wins, data.results.fighter2_wins, data.results.draws]);
      showStats(data.fighter1, data.fighter2, data);
    } catch (err) {
      showStatus('Error: ' + err.message);
    }
  });
});
