/* No charting dependency or remote requests. Only touches #benchmarks. */
(() => {
  'use strict';
  const root = document.getElementById('benchmarks');
  const data = window.UGG_BENCHMARKS;
  if (!root || !data) return;
  const $ = selector => root.querySelector(selector);
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const arrow = metric => metric.direction === 'up' ? '↑' : '↓';
  const format = (value, metric) => Number(value).toFixed(metric.digits);
  const kind = method => data.methods[method].kind || 'baseline';
  const state = { task: 0, settings: {}, dataset: 'all', oracle: false };
  let observer;
  const chartNote = $('.bm-chart-note').textContent;
  const currentTask = () => data.tasks[state.task];
  const currentSetting = () => currentTask().settings[state.settings[currentTask().key] || 0];
  const visibleRows = setting => setting.rows.filter(row => kind(row.method) !== 'oracle' || state.oracle);

  // Use one ranking rule for every chart and table, not method identity.
  // Compare source values (not rounded labels), include ties, and exclude Oracle.
  const comparisonBlocks = setting => setting.blocks || [setting.rows.filter(row => kind(row.method) !== 'oracle').map(row => row.method)];
  function isBestInBlock(setting, row, column) {
    if (kind(row.method) === 'oracle') return false;
    const block = comparisonBlocks(setting).find(items => items.includes(row.method));
    const candidates = setting.rows.filter(other => block?.includes(other.method) && kind(other.method) !== 'oracle');
    if (!candidates.length) return false;
    const metric = setting.metrics[column % setting.metrics.length];
    const best = (metric.direction === 'up' ? Math.max : Math.min)(...candidates.map(other => other.values[column]));
    return row.values[column] === best;
  }

  // All scales start at zero. Never normalize or invert errors into scores.
  function axisMax(values) {
    const max = Math.max(...values);
    if (!max) return 1;
    const magnitude = Math.pow(10, Math.floor(Math.log10(max)));
    return Math.ceil(max * 1.12 / magnitude * 5) / 5 * magnitude;
  }
  function chart(setting, datasetIndex, metricIndex, chartRows) {
    const ablation = currentTask().key === 'ablations';
    const metric = setting.metrics[metricIndex];
    const column = datasetIndex * setting.metrics.length + metricIndex;
    const values = chartRows.map(row => row.values[column]);
    const top = axisMax(values), left = 42, right = 352, baseline = 184, height = 149;
    const slot = (right - left) / chartRows.length, width = Math.min(46, slot * .67);
    const name = `${setting.datasets[datasetIndex]} · ${metric.label} ${arrow(metric)}`;
    let svg = `<svg class="bm-chart${ablation ? ' bm-ablation-chart' : ''}" viewBox="0 0 364 207" role="group" aria-label="${escape(name)}"><title>${escape(name)}</title>`;
    [0, .5, 1].forEach(fraction => {
      const y = baseline - height * fraction;
      const tick = +(top * fraction).toPrecision(3);
      svg += `<line class="${fraction ? 'bm-gridline' : 'bm-baseline'}" x1="${left}" x2="${right}" y1="${y}" y2="${y}"/><text class="bm-tick" x="${left - 7}" y="${y + 3}" text-anchor="end">${escape(tick)}</text>`;
    });
    if (setting.blocks) {
      setting.blocks.forEach((block, index) => {
        const first = chartRows.findIndex(row => block.includes(row.method));
        const count = chartRows.filter(row => block.includes(row.method)).length;
        if (first < 0) return;
        const x = left + slot * first;
        if (index) svg += `<line class="bm-block-separator" x1="${x}" x2="${x}" y1="28" y2="${baseline}"/>`;
        svg += `<text class="bm-block-label" x="${x + slot * count / 2}" y="201" text-anchor="middle">Block ${index + 1}</text>`;
      });
    }
    chartRows.forEach((row, index) => {
      const method = data.methods[row.method], value = row.values[column];
      const best = isBestInBlock(setting, row, column);
      const center = left + slot * (index + .5), barHeight = value / top * height, y = baseline - barHeight;
      const label = `${method.label}: ${format(value, metric)}${kind(row.method) === 'oracle' ? ' (oracle reference)' : ''}${best ? ' (best non-oracle result in comparison block)' : ''}`;
      svg += `<g class="bm-bar bm-${kind(row.method)}${best ? ' bm-best' : ''}" style="--bm-color:${method.color}" tabindex="0" role="img" aria-label="${escape(label)}" data-method="${escape(row.method)}" data-value="${value}"><title>${escape(label)}</title><rect x="${center - width / 2}" y="${y}" width="${width}" height="${barHeight}" rx="3"/><text class="bm-value" x="${center}" y="${y - 8}" text-anchor="middle">${format(value, metric)}</text></g>`;
    });
    return `<figure class="bm-metric"><figcaption>${escape(metric.label)} <span>${arrow(metric)}</span></figcaption>${svg}</svg></figure>`;
  }
  function renderCharts() {
    const task = currentTask(), setting = currentSetting(), chartRows = visibleRows(setting);
    $('#bm-context').textContent = `${task.title} · ${setting.caption}`;
    $('#bm-note').textContent = task.note;
    $('.bm-chart-note').textContent = chartNote
      + ' Bold values mark the best non-oracle result per metric within each comparison block, including ties.'
      + (setting.blocks ? ' Block 1: task / architecture. Block 2: camera representation. Blocks are ranked separately, as in Table 4b.' : '')
      + (task.key === 'depth' ? ' TTS Oracle is a separate reference and is not ranked, whether shown or hidden.' : '');
    $('#bm-paper').href = `assets/ugg-paper.pdf#page=${task.page}`;
    $('#bm-paper').textContent = `Paper · Table ${setting.table} ↗`;
    $('#bm-oracle-control').hidden = !task.settings.some(setting => setting.rows.some(row => kind(row.method) === 'oracle'));
    $('#bm-legend').innerHTML = chartRows.map(row => {
      const method = data.methods[row.method];
      return `<span class="bm-legend-item bm-${kind(row.method)}" style="--bm-color:${method.color}"><i class="bm-swatch" aria-hidden="true"></i>${escape(method.label)}${kind(row.method) === 'oracle' ? ' †' : ''}</span>`;
    }).join('');
    if (observer) observer.disconnect();
    $('#bm-charts').innerHTML = setting.datasets.map((dataset, datasetIndex) => {
      if (state.dataset !== 'all' && state.dataset !== dataset) return '';
      return `<article class="bm-dataset" aria-label="${escape(dataset)}"><div class="bm-dataset-heading"><h3>${escape(dataset)}</h3><span>Table ${setting.table} · ${escape(setting.label)}</span></div><div class="bm-metrics">${setting.metrics.map((_, index) => chart(setting, datasetIndex, index, chartRows)).join('')}</div></article>`;
    }).join('');
    const chartCards = root.querySelectorAll('.bm-dataset');
    if ('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      observer = new IntersectionObserver(entries => entries.forEach(entry => {
        if (entry.isIntersecting) { entry.target.classList.add('bm-grown'); observer.unobserve(entry.target); }
      }), { threshold: .12 });
      chartCards.forEach(card => observer.observe(card));
    } else chartCards.forEach(card => card.classList.add('bm-grown'));
    $('#bm-status').textContent = `${task.title}, ${setting.label}, ${state.dataset === 'all' ? 'all datasets' : state.dataset}. ${chartRows.length} methods or variants shown.`;
  }
  function renderFilters() {
    const task = currentTask(), setting = currentSetting();
    $('#bm-modes').innerHTML = task.settings.map((item, index) => `<button type="button" data-mode="${index}" aria-pressed="${item === setting}">${escape(item.label)}</button>`).join('');
    updateDatasetOptions();
  }
  function updateDatasetOptions() {
    const setting = currentSetting();
    if (!setting.datasets.includes(state.dataset)) state.dataset = 'all';
    $('#bm-dataset').innerHTML = '<option value="all">All datasets</option>' + setting.datasets.map(name => `<option value="${escape(name)}">${escape(name)}</option>`).join('');
    $('#bm-dataset').value = state.dataset;
  }
  function renderTable(setting) {
    const columns = setting.datasets.flatMap(dataset => setting.metrics.map(metric => ({dataset, metric})));
    const blocks = comparisonBlocks(setting);
    const tableRows = setting.rows.map(row => {
      const method = data.methods[row.method];
      const separator = blocks.slice(1).some(items => items[0] === row.method);
      const cells = row.values.map((value, index) => {
        const metric = columns[index].metric;
        const best = isBestInBlock(setting, row, index);
        return `<td${best ? ' class="bm-best"' : ''}>${format(value, metric)}</td>`;
      }).join('');
      return `<tr class="bm-${kind(row.method)}${separator ? ' bm-break' : ''}"><th scope="row">${escape(method.label)}${kind(row.method) === 'oracle' ? ' †' : ''}</th>${cells}</tr>`;
    }).join('');
    return `<h3 class="bm-table-title">Table ${setting.table} · ${escape(setting.label)}</h3><div class="bm-scroll" role="region" aria-label="Table ${setting.table}, ${escape(setting.label)}" tabindex="0"><table><caption>${escape(setting.caption)}</caption><thead><tr><th scope="col" rowspan="2">Method / variant</th>${setting.datasets.map(name => `<th scope="colgroup" colspan="${setting.metrics.length}">${escape(name)}</th>`).join('')}</tr><tr>${columns.map(({metric}) => `<th scope="col">${escape(metric.label)} ${arrow(metric)}</th>`).join('')}</tr></thead><tbody>${tableRows}</tbody></table></div>`;
  }
  function renderTables() {
    $('#bm-table-body').innerHTML = currentTask().settings.map(renderTable).join('');
  }
  function selectTask(index) {
    state.task = index;
    state.dataset = 'all';
    root.querySelectorAll('.bm-tab').forEach((tab, i) => {
      tab.setAttribute('aria-selected', String(i === index));
      tab.tabIndex = i === index ? 0 : -1;
    });
    $('#bm-panel').setAttribute('aria-labelledby', `bm-tab-${currentTask().key}`);
    renderFilters(); renderCharts(); renderTables();
  }
  function downloadCSV() {
    const task = currentTask();
    const records = [['Task', 'Table', 'Setting', 'Dataset', 'Method', 'Metric', 'Direction', 'Value', 'Oracle reference']];
    task.settings.forEach(setting => setting.datasets.forEach((dataset, di) => setting.rows.forEach(row => setting.metrics.forEach((metric, mi) => {
      records.push([task.title, setting.table, setting.label, dataset, data.methods[row.method].label, metric.label, metric.direction === 'up' ? 'higher is better' : 'lower is better', format(row.values[di * setting.metrics.length + mi], metric), kind(row.method) === 'oracle' ? 'yes' : 'no']);
    }))));
    const csv = records.map(record => record.map(value => `"${String(value).replace(/"/g, '""')}"`).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' }));
    const a = document.createElement('a');
    a.href = url; a.download = `ugg-${task.key}-benchmarks.csv`;
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  try {
    let count = 0;
    data.tasks.forEach(task => task.settings.forEach(setting => setting.rows.forEach(row => {
      if (!data.methods[row.method] || row.values.length !== setting.datasets.length * setting.metrics.length || row.values.some(value => !Number.isFinite(value) || value < 0)) throw new Error('Invalid benchmark data');
      count += row.values.length;
    })));
    if (count !== data.source.valueCount) throw new Error('Incomplete benchmark data');
    $('#bm-tabs').innerHTML = data.tasks.map((task, index) => `<button class="bm-tab" id="bm-tab-${task.key}" role="tab" type="button" aria-controls="bm-panel" aria-selected="${index === 0}" tabindex="${index === 0 ? 0 : -1}" data-task="${index}">${escape(task.label)}</button>`).join('');
    $('#bm-tabs').addEventListener('click', event => {
      const tab = event.target.closest('[data-task]');
      if (tab) selectTask(Number(tab.dataset.task));
    });
    $('#bm-tabs').addEventListener('keydown', event => {
      const tab = event.target.closest('[data-task]');
      if (!tab || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      let index = Number(tab.dataset.task);
      if (event.key === 'Home') index = 0;
      else if (event.key === 'End') index = data.tasks.length - 1;
      else index = (index + (event.key === 'ArrowRight' ? 1 : -1) + data.tasks.length) % data.tasks.length;
      selectTask(index); root.querySelectorAll('.bm-tab')[index].focus();
    });
    $('#bm-modes').addEventListener('click', event => {
      const button = event.target.closest('[data-mode]');
      if (!button) return;
      const index = Number(button.dataset.mode);
      state.settings[currentTask().key] = index;
      root.querySelectorAll('[data-mode]').forEach((item, i) => item.setAttribute('aria-pressed', String(i === index)));
      updateDatasetOptions(); renderCharts();
    });
    $('#bm-dataset').addEventListener('change', event => { state.dataset = event.target.value; renderCharts(); });
    $('#bm-oracle').addEventListener('change', event => { state.oracle = event.target.checked; renderCharts(); });
    $('#bm-download').addEventListener('click', downloadCSV);
    selectTask(0);
    $('#bm-app').hidden = false;
    $('#bm-fallback').hidden = true;
  } catch (error) {
    // Keep the paper link usable if an edit introduces malformed data or markup.
    console.error('UGG benchmarks:', error);
    $('#bm-fallback').hidden = false;
    $('#bm-app').hidden = true;
  }
})();
