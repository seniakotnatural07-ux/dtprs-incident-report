// Демо-дашборд: рендерит docs/data.json (только тестовые данные, см. generate_dashboard_data.py)

function fmtMinutes(total) {
  total = Math.round(total);
  const days = Math.floor(total / (24 * 60));
  const hours = Math.floor((total % (24 * 60)) / 60);
  const minutes = total % 60;
  const parts = [];
  if (days) parts.push(`${days} сут.`);
  parts.push(`${hours} ч.`);
  parts.push(`${minutes} мин.`);
  return parts.join(' ');
}

function el(tag, opts = {}, children = []) {
  const node = document.createElement(tag);
  Object.entries(opts).forEach(([key, value]) => {
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key === 'html') node.innerHTML = value;
    else node.setAttribute(key, value);
  });
  children.forEach((c) => node.appendChild(c));
  return node;
}

function renderKpis(kpi) {
  const grid = document.getElementById('kpi-grid');
  const tiles = [
    ['Всего аварий', kpi.total_incidents, 'num'],
    ['Простой >8ч', kpi.gt8h_count, 'num'],
    ['Общий простой', fmtMinutes(kpi.total_downtime_minutes), 'text'],
    ['Средний простой', fmtMinutes(kpi.avg_downtime_minutes), 'text'],
    ['Проблемный город', kpi.problem_city, 'text'],
    ['Частый объект', kpi.frequent_node, 'text'],
  ];
  tiles.forEach(([label, value, kind]) => {
    grid.appendChild(el('div', { class: 'card kpi-tile' }, [
      el('p', { class: 'kpi-label', text: label }),
      el('p', { class: `kpi-value ${kind === 'text' ? 'text' : ''}`, text: String(value) }),
    ]));
  });
}

// Горизонтальный барчарт — одна серия (кол-во аварий), прямые подписи значений.
function renderHBarChart(containerId, rows, labelKey) {
  const container = document.getElementById(containerId);
  if (!rows.length) {
    container.appendChild(el('p', { class: 'empty', text: 'Нет данных' }));
    return;
  }
  const max = Math.max(...rows.map((r) => r.count));
  rows.forEach((r) => {
    const pct = Math.max((r.count / max) * 100, 4);
    container.appendChild(el('div', { class: 'hbar-row' }, [
      el('div', { class: 'hbar-label', text: r[labelKey] }),
      el('div', { class: 'hbar-track' }, [
        el('div', { class: 'hbar-fill', style: `width:${pct}%` }),
      ]),
      el('div', { class: 'hbar-value', text: String(r.count) }),
    ]));
  });
}

// Вертикальный барчарт для динамики по дням.
function renderVBarChart(containerId, rows) {
  const container = document.getElementById(containerId);
  container.classList.add('vbar-chart');
  if (!rows.length) {
    container.appendChild(el('p', { class: 'empty', text: 'Нет данных' }));
    return;
  }
  const max = Math.max(...rows.map((r) => r.count));
  rows.forEach((r) => {
    const pct = Math.max((r.count / max) * 100, 6);
    container.appendChild(el('div', { class: 'vbar-col' }, [
      el('div', { class: 'vbar-value', text: String(r.count) }),
      el('div', { class: 'vbar-fill', style: `height:${pct}%` }),
      el('div', { class: 'vbar-label', text: r.date }),
    ]));
  });
}

function renderNodesTable(rows) {
  const container = document.getElementById('table-nodes');
  if (!rows.length) {
    container.appendChild(el('p', { class: 'empty', text: 'Нет данных' }));
    return;
  }
  const table = el('table', {}, [
    el('thead', {}, [
      el('tr', {}, [
        el('th', { text: 'Узел сети' }),
        el('th', { text: 'Город' }),
        el('th', { text: 'Зона' }),
        el('th', { text: 'Аварий' }),
        el('th', { text: 'Общий простой' }),
      ]),
    ]),
  ]);
  const tbody = el('tbody');
  rows.forEach((r) => {
    tbody.appendChild(el('tr', {}, [
      el('td', { text: r.node }),
      el('td', { text: r.city }),
      el('td', { text: r.zone }),
      el('td', { text: String(r.count) }),
      el('td', { text: fmtMinutes(r.total_minutes) }),
    ]));
  });
  table.appendChild(tbody);
  container.appendChild(table);
}

function renderEscalationsTable(rows) {
  const container = document.getElementById('table-escalations');
  if (!rows.length) {
    container.appendChild(el('p', { class: 'empty', text: 'Аварий с простоем более 8 часов нет.' }));
    return;
  }
  const table = el('table', {}, [
    el('thead', {}, [
      el('tr', {}, [
        el('th', { text: 'Город' }),
        el('th', { text: 'Объект' }),
        el('th', { text: 'Зона' }),
        el('th', { text: 'Начало' }),
        el('th', { text: 'Простой' }),
      ]),
    ]),
  ]);
  const tbody = el('tbody');
  rows.forEach((r) => {
    tbody.appendChild(el('tr', {}, [
      el('td', { text: r.city }),
      el('td', { text: r.node }),
      el('td', { text: r.zone }),
      el('td', { text: r.started_at }),
      el('td', {}, [el('span', { class: 'badge critical', text: `⚠ ${r.duration_text}` })]),
    ]));
  });
  table.appendChild(tbody);
  container.appendChild(table);
}

async function main() {
  const res = await fetch('data.json', { cache: 'no-store' });
  const data = await res.json();

  const generatedAt = new Date(data.generated_at);
  document.getElementById('generated-at').textContent =
    `Сформировано: ${generatedAt.toLocaleString('ru-RU')}`;

  renderKpis(data.kpi);
  renderHBarChart('chart-city', data.by_city, 'city');
  renderHBarChart('chart-zone', data.by_zone, 'zone');
  renderVBarChart('chart-daily', data.daily);
  renderNodesTable(data.top_nodes);
  renderEscalationsTable(data.escalations);
}

main().catch((err) => {
  document.querySelector('.wrap').appendChild(
    el('p', { class: 'empty', text: `Не удалось загрузить данные: ${err}` })
  );
});
