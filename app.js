/**
 * 首銷日報機器人 - 前端核心邏輯
 * 
 * 功能：
 * 1. TSV 數據解析（飛書表格直接貼上）
 * 2. 飛書卡片 JSON 生成
 * 3. 預覽渲染
 */

// ===== 指標映射 =====
const METRIC_MAP = {
  '首銷目標': 'target', '目标': 'target', 'target': 'target',
  '已達成': 'achieved', '已达成': 'achieved', 'achieved': 'achieved',
  '達成率': 'achievement_rate', '达成率': 'achievement_rate',
  '落後時間進度': 'behind_time_progress', '落后时间进度': 'behind_time_progress',
  '上代同期': 'previous_gen_total',
  'YOY': 'yoy', 'yoy': 'yoy',
  '時間進度': 'time_progress', '时间进度': 'time_progress',
  '首銷日期': 'launch_date', '首销日期': 'launch_date',
  '報告日期': 'report_date', '报告日期': 'report_date',
  'DAY': 'day_number', 'day': 'day_number',
  '標題': 'title', '标题': 'title', 'title': 'title',
  '產品佔比': 'product_mix', '产品占比': 'product_mix',
  '上代佔比': 'product_mix_prev', '上代占比': 'product_mix_prev',
};

const CHANNEL_MAP = {
  '米网': '米網', '米店': '米店', '運營商': '運營商', '运营商': '運營商',
  'KA': 'KA', 'GC': 'GC&澳門', 'GC&澳門': 'GC&澳門', 'gc': 'GC&澳門',
};

// ===== 工具函數 =====
function numStr(v) {
  if (v == null || isNaN(v)) return '—';
  return Number(v).toLocaleString();
}

function safeDiv(a, b) {
  if (!b || b === 0) return null;
  return a / b * 100;
}

// ===== TSV 解析 =====
function parseTSV(text) {
  const lines = text.split('\n').map(l => l.trim()).filter(l => l);
  if (!lines.length) throw new Error('數據為空');

  // 按表頭偵測分段
  const headerKw = new Set(['日期', 'date', '產品', '产品', '渠道', 'channel',
    '配置', 'config', '顏色', '颜色', 'color']);
  
  const segments = [];
  let current = [];
  
  for (const line of lines) {
    const cols = line.split('\t').map(c => c.trim().toLowerCase());
    const firstCol = cols[0];
    const isHeader = headerKw.has(firstCol) && cols.length >= 2;
    
    if (isHeader && current.length) {
      segments.push(current);
      current = [];
    }
    current.push(line);
  }
  if (current.length) segments.push(current);

  // 解析結果
  const result = {
    summary: {},
    daily_so: { dates: [], current_gen: [], previous_gen: [] },
    product_breakdown: {},
    channel_breakdown: [],
    config_mix: { current: [], previous: [] },
    color_mix: { current: [], previous: [] },
  };

  for (const seg of segments) {
    const header = seg[0].split('\t').map(h => h.trim());
    const rows = seg.slice(1);
    const headerJoined = header.join(' ').toLowerCase();

    if (header.some(h => /日期|date/i.test(h))) {
      parseDailySO(header, rows, result);
    } else if (/產品|产品|P12U|P12A/.test(headerJoined)) {
      parseProduct(header, rows, result);
    } else if (/渠道|channel|米網|米网|KA/.test(headerJoined)) {
      parseChannel(header, rows, result);
    } else if (/配置|config/i.test(headerJoined)) {
      parseConfig(header, rows, result);
    } else if (/顏色|颜色|color/i.test(headerJoined)) {
      parseColor(header, rows, result);
    } else {
      parseSummary(header, rows, result);
    }
  }

  return result;
}

function findCol(header, candidates) {
  // 精確匹配優先
  for (let i = 0; i < header.length; i++) {
    const h = header[i].trim().toLowerCase();
    for (const c of candidates) {
      if (h === c.toLowerCase()) return i;
    }
  }
  // 包含匹配（長關鍵詞）
  for (let i = 0; i < header.length; i++) {
    const h = header[i].trim().toLowerCase();
    for (const c of candidates) {
      if (c.length >= 3 && c.toLowerCase() in h && h !== c.toLowerCase()) return i;
    }
  }
  return -1;
}

function parseNum(s) {
  if (!s || s === '—' || s === '-' || s === 'N/A') return null;
  const clean = s.replace(/[,+%]/g, '').trim();
  const n = Number(clean);
  return isNaN(n) ? null : n;
}

function parseSummary(header, rows, result) {
  for (const row of rows) {
    const cols = row.split('\t');
    if (cols.length < 2) continue;
    const key = cols[0].trim();
    const val = cols[1].trim();
    const eng = METRIC_MAP[key] || key;

    if (typeof eng === 'object') {
      // 產品側
      const { product, field } = eng;
      if (!result.product_breakdown[product]) result.product_breakdown[product] = {};
      result.product_breakdown[product][field || 'achieved'] = parseNum(val);
    } else if (eng === 'product_mix') {
      result.product_breakdown._mix = result.product_breakdown._mix || {};
      result.product_breakdown._mix.current = val;
    } else if (eng === 'product_mix_prev') {
      result.product_breakdown._mix = result.product_breakdown._mix || {};
      result.product_breakdown._mix.previous = val;
    } else {
      result.summary[eng] = ['launch_date', 'report_date', 'title'].includes(eng) ? val : parseNum(val);
    }
  }
}

function parseDailySO(header, rows, result) {
  const dateIdx = findCol(header, ['日期', 'date']);
  const soIdx = findCol(header, ['SO', 'so', '激活', 'active']);
  const prevIdx = findCol(header, ['上代SO', '上代', 'previous', 'O代', 'O12']);

  for (const row of rows) {
    const cols = row.split('\t');
    if (cols.length <= Math.max(dateIdx, soIdx)) continue;
    result.daily_so.dates.push(cols[dateIdx].trim());
    result.daily_so.current_gen.push(parseNum(cols[soIdx].trim()));
    if (prevIdx >= 0 && prevIdx < cols.length) {
      result.daily_so.previous_gen.push(parseNum(cols[prevIdx].trim()));
    }
  }
}

function parseProduct(header, rows, result) {
  const nameIdx = findCol(header, ['產品', '产品', 'name', '系列']);
  const targetIdx = findCol(header, ['目標', '目标', 'target']);
  const achievedIdx = findCol(header, ['已達成', '已达成', 'achieved', 'SO']);
  const yoyIdx = findCol(header, ['YOY', 'yoy', '同比']);

  for (const row of rows) {
    const cols = row.split('\t');
    if (cols.length <= Math.max(nameIdx, achievedIdx)) continue;
    const name = cols[nameIdx].trim();
    result.product_breakdown[name] = {
      target: targetIdx >= 0 && targetIdx < cols.length ? parseNum(cols[targetIdx].trim()) : null,
      achieved: parseNum(cols[achievedIdx].trim()),
      yoy: yoyIdx >= 0 && yoyIdx < cols.length ? parseNum(cols[yoyIdx].trim()) : null,
    };
  }
}

function parseChannel(header, rows, result) {
  const nameIdx = findCol(header, ['渠道', 'channel', '名稱', '名称']);
  const targetIdx = findCol(header, ['目標', '目标', 'target']);
  const achievedIdx = findCol(header, ['已達成', '已达成', 'achieved', 'SO']);
  const yoyIdx = findCol(header, ['YOY', 'yoy', '同比']);

  for (const row of rows) {
    const cols = row.split('\t');
    if (cols.length <= Math.max(nameIdx, achievedIdx)) continue;
    const name = CHANNEL_MAP[cols[nameIdx].trim()] || cols[nameIdx].trim();
    result.channel_breakdown.push({
      name,
      target: targetIdx >= 0 && targetIdx < cols.length ? parseNum(cols[targetIdx].trim()) : null,
      achieved: parseNum(cols[achievedIdx].trim()),
      yoy: yoyIdx >= 0 && yoyIdx < cols.length ? parseNum(cols[yoyIdx].trim()) : null,
    });
  }
}

function parseConfig(header, rows, result) {
  const nameIdx = findCol(header, ['配置', 'config', '名稱', '名称']);
  const currIdx = findCol(header, ['本代', '當前', 'current', 'P12']);
  const prevIdx = findCol(header, ['上代', 'O代', 'previous', 'O12']);

  for (const row of rows) {
    const cols = row.split('\t');
    if (cols.length <= Math.max(nameIdx, currIdx)) continue;
    result.config_mix.current.push({ name: cols[nameIdx].trim(), value: parseNum(cols[currIdx].trim()) });
    if (prevIdx >= 0 && prevIdx < cols.length && cols[prevIdx].trim()) {
      result.config_mix.previous.push({ name: cols[nameIdx].trim(), value: parseNum(cols[prevIdx].trim()) });
    }
  }
}

function parseColor(header, rows, result) {
  const nameIdx = findCol(header, ['顏色', '颜色', 'color', '名稱', '名称']);
  const currIdx = findCol(header, ['本代', '當前', 'current', 'P12']);
  const prevIdx = findCol(header, ['上代', 'O代', 'previous', 'O12']);

  for (const row of rows) {
    const cols = row.split('\t');
    if (cols.length <= Math.max(nameIdx, currIdx)) continue;
    result.color_mix.current.push({ name: cols[nameIdx].trim(), value: parseNum(cols[currIdx].trim()) });
    if (prevIdx >= 0 && prevIdx < cols.length && cols[prevIdx].trim()) {
      result.color_mix.previous.push({ name: cols[nameIdx].trim(), value: parseNum(cols[prevIdx].trim()) });
    }
  }
}

// ===== 卡片生成 =====
function buildCard(data, title) {
  const s = data.summary;
  const components = [];

  // 1. KPI 指標卡
  const kpiItems = [];
  if (s.target != null) kpiItems.push({ title: '首銷目標', value: numStr(s.target) });
  if (s.achieved != null) kpiItems.push({ title: '已達成', value: numStr(s.achieved) });
  const rate = s.achievement_rate || safeDiv(s.achieved, s.target);
  if (rate != null) kpiItems.push({ title: '達成率', value: rate.toFixed(1) + '%' });
  if (s.behind_time_progress != null) kpiItems.push({ title: '落後時間進度', value: s.behind_time_progress.toFixed(1) + 'pp' });
  if (s.previous_gen_total != null) kpiItems.push({ title: '上代同期', value: numStr(s.previous_gen_total) });
  if (s.yoy != null) kpiItems.push({ title: 'YOY', value: s.yoy.toFixed(1) + '%' });
  if (kpiItems.length) components.push({ type: 'kpi_group', items: kpiItems });

  // 2. 每日SO趨勢
  const { dates, current_gen, previous_gen } = data.daily_so;
  if (dates.length && current_gen.length) {
    const chartData = [];
    for (let i = 0; i < dates.length; i++) {
      chartData.push({ date: dates[i], value: current_gen[i] || 0, series: title });
      if (i < previous_gen.length) chartData.push({ date: dates[i], value: previous_gen[i], series: '上代' });
    }
    components.push({ type: 'text', content: '**📈 每日SO趨勢**', text_size: 'heading-4' });
    components.push({ type: 'line', x: 'date', y: 'value', series: 'series', data: chartData, height: '280px' });
  }

  // 3. 產品側
  const productRows = Object.entries(data.product_breakdown)
    .filter(([k]) => !k.startsWith('_'))
    .map(([name, p]) => ({
      product: name,
      target: numStr(p.target),
      achieved: numStr(p.achieved),
      rate: p.target ? safeDiv(p.achieved, p.target).toFixed(1) + '%' : '—',
      yoy: p.yoy != null ? p.yoy.toFixed(1) + '%' : '—',
    }));
  if (productRows.length) {
    components.push({ type: 'text', content: '**📱 產品側**', text_size: 'heading-4' });
    components.push({
      type: 'table',
      columns: [
        { key: 'product', name: '產品' },
        { key: 'target', name: '目標', data_type: 'text', horizontal_align: 'right' },
        { key: 'achieved', name: '已達成', data_type: 'text', horizontal_align: 'right' },
        { key: 'rate', name: '達成率', data_type: 'text', horizontal_align: 'right' },
        { key: 'yoy', name: 'YOY', data_type: 'text', horizontal_align: 'right' },
      ],
      rows: productRows,
    });
  }

  // 產品佔比
  const mix = data.product_breakdown._mix;
  if (mix) {
    components.push({ type: 'text', content: `**產品佔比**：${mix.current || '—'} vs 上代 ${mix.previous || '—'}` });
  }

  // 4. 配置佔比
  if (data.config_mix.current.length) {
    components.push({ type: 'text', content: '**⚙️ 配置佔比**', text_size: 'heading-4' });
    const allCfgs = [...new Set([...data.config_mix.current, ...(data.config_mix.previous || [])].map(c => c.name))].sort();
    const cfgRows = allCfgs.map(name => {
      const curr = data.config_mix.current.find(c => c.name === name);
      const prev = (data.config_mix.previous || []).find(c => c.name === name);
      return { config: name, '本代': curr ? curr.value.toFixed(1) + '%' : '—', '上代': prev ? prev.value.toFixed(1) + '%' : '—' };
    });
    components.push({
      type: 'table',
      columns: [
        { key: 'config', name: '配置' },
        { key: '本代', name: '本代', data_type: 'text', horizontal_align: 'right' },
        { key: '上代', name: '上代', data_type: 'text', horizontal_align: 'right' },
      ],
      rows: cfgRows,
    });
  }

  // 5. 顏色佔比
  if (data.color_mix.current.length) {
    components.push({ type: 'text', content: '**🎨 顏色佔比**', text_size: 'heading-4' });
    const allColors = [...new Set([...data.color_mix.current, ...(data.color_mix.previous || [])].map(c => c.name))].sort();
    const colorRows = allColors.map(name => {
      const curr = data.color_mix.current.find(c => c.name === name);
      const prev = (data.color_mix.previous || []).find(c => c.name === name);
      return { color: name, '本代': curr ? curr.value.toFixed(1) + '%' : '—', '上代': prev ? prev.value.toFixed(1) + '%' : '—' };
    });
    components.push({
      type: 'table',
      columns: [
        { key: 'color', name: '顏色' },
        { key: '本代', name: '本代', data_type: 'text', horizontal_align: 'right' },
        { key: '上代', name: '上代', data_type: 'text', horizontal_align: 'right' },
      ],
      rows: colorRows,
    });
  }

  // 6. 渠道側
  if (data.channel_breakdown.length) {
    components.push({ type: 'text', content: '**📊 渠道側**', text_size: 'heading-4' });
    let totalTarget = 0, totalAchieved = 0;
    const chRows = data.channel_breakdown.map(ch => {
      const rate = safeDiv(ch.achieved, ch.target);
      if (ch.target) totalTarget += ch.target;
      if (ch.achieved) totalAchieved += ch.achieved;
      return {
        channel: ch.name,
        target: numStr(ch.target),
        achieved: numStr(ch.achieved),
        rate: rate != null ? rate.toFixed(1) + '%' : '—',
        yoy: ch.yoy != null ? ch.yoy.toFixed(1) + '%' : '—',
      };
    });
    const totalRate = safeDiv(totalAchieved, totalTarget);
    chRows.push({
      channel: '📊 合計',
      target: numStr(totalTarget),
      achieved: numStr(totalAchieved),
      rate: totalRate != null ? totalRate.toFixed(1) + '%' : '—',
      yoy: '—',
    });
    components.push({
      type: 'table',
      columns: [
        { key: 'channel', name: '渠道' },
        { key: 'target', name: '目標', data_type: 'text', horizontal_align: 'right' },
        { key: 'achieved', name: '已達成', data_type: 'text', horizontal_align: 'right' },
        { key: 'rate', name: '達成率', data_type: 'text', horizontal_align: 'right' },
        { key: 'yoy', name: 'YOY', data_type: 'text', horizontal_align: 'right' },
      ],
      rows: chRows,
    });
  }

  // 7. 口徑說明
  const launch = s.launch_date || '';
  components.push({ type: 'text', content: `<font color='grey'>📋 首銷期: ${launch} 起 | 數據口徑: 銷售激活 | 數據來源: 國際BI</font>` });

  // 組裝
  const subtitleParts = [];
  if (s.day_number) subtitleParts.push(`DAY ${s.day_number}`);
  if (s.report_date) subtitleParts.push(String(s.report_date));
  if (s.time_progress) subtitleParts.push(`時間進度${s.time_progress}%`);

  return {
    card: {
      title: `📊 ${title}首銷激活進展`,
      subtitle: subtitleParts.join(' | '),
      components,
    },
  };
}

// ===== 渲染預覽（簡易 HTML） =====
function renderPreview(card) {
  const el = document.getElementById('preview');
  const c = card.card;
  let html = `<div style="padding:16px;">`;
  html += `<h3 style="color:#3370ff;margin-bottom:4px;">${c.title}</h3>`;
  html += `<p style="color:#8f959e;font-size:13px;margin-bottom:16px;">${c.subtitle}</p>`;

  for (const comp of c.components) {
    if (comp.type === 'kpi_group') {
      html += '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;">';
      for (const item of comp.items) {
        html += `<div style="flex:1;min-width:80px;background:#f5f6f7;padding:12px;border-radius:8px;text-align:center;">
          <div style="font-size:11px;color:#8f959e;">${item.title}</div>
          <div style="font-size:18px;font-weight:700;color:#1f2329;">${item.value}</div>
        </div>`;
      }
      html += '</div>';
    } else if (comp.type === 'text') {
      html += `<div style="margin:12px 0;font-size:14px;">${comp.content.replace(/\*\*/g, '').replace(/<[^>]+>/g, '')}</div>`;
    } else if (comp.type === 'table') {
      html += '<table style="width:100%;border-collapse:collapse;font-size:13px;margin:8px 0;">';
      html += '<thead><tr>';
      for (const col of comp.columns) {
        const align = col.horizontal_align === 'right' ? 'text-align:right;' : '';
        html += `<th style="padding:8px;border-bottom:2px solid #dee0e3;font-weight:600;${align}">${col.name}</th>`;
      }
      html += '</tr></thead><tbody>';
      for (const row of comp.rows) {
        html += '<tr>';
        for (const col of comp.columns) {
          const align = col.horizontal_align === 'right' ? 'text-align:right;' : '';
          html += `<td style="padding:8px;border-bottom:1px solid #f0f1f2;${align}">${row[col.key] || '—'}</td>`;
        }
        html += '</tr>';
      }
      html += '</tbody></table>';
    }
  }
  html += '</div>';
  el.innerHTML = html;
}

// ===== 全局狀態 =====
let currentCard = null;
let currentTitle = 'P12系列';

// ===== UI 交互 =====
function showSection(name) {
  document.querySelectorAll('.section').forEach(s => s.style.display = 'none');
  document.getElementById(name).style.display = 'block';
  document.querySelectorAll('.nav-links a').forEach(a => a.classList.remove('active'));
  event.target.classList.add('active');
}

function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
}

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2000);
}

function generateReport() {
  const title = document.getElementById('productTitle').value.trim();
  const tsv = document.getElementById('tsvInput').value.trim();

  if (!tsv) {
    showToast('❌ 請先貼入數據');
    return;
  }

  try {
    currentTitle = title || 'P12系列';
    const data = parseTSV(tsv);

    // 驗證
    if (!data.summary.target && !data.summary.achieved) {
      showToast('⚠️ 未找到核心指標（首銷目標/已達成），請檢查數據格式');
      return;
    }

    currentCard = buildCard(data, currentTitle);
    renderPreview(currentCard);
    document.getElementById('previewActions').style.display = 'flex';
    showToast('✅ 日報生成成功！');
  } catch (e) {
    showToast('❌ 解析失敗: ' + e.message);
    console.error(e);
  }
}

function copyJSON() {
  if (!currentCard) return;
  navigator.clipboard.writeText(JSON.stringify(currentCard, null, 2))
    .then(() => showToast('✅ JSON 已複製到剪貼板'))
    .catch(() => showToast('❌ 複製失敗'));
}

function downloadJSON() {
  if (!currentCard) return;
  const blob = new Blob([JSON.stringify(currentCard, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${currentTitle}_首銷日報.json`;
  a.click();
  URL.revokeObjectURL(url);
  showToast('✅ 文件已下載');
}

function copyMarkdown() {
  if (!currentCard) return;
  const md = generateMarkdown(currentCard);
  navigator.clipboard.writeText(md)
    .then(() => showToast('✅ Markdown 已複製'))
    .catch(() => showToast('❌ 複製失敗'));
}

function generateMarkdown(card) {
  const c = card.card;
  let md = `# ${c.title}\n\n> ${c.subtitle}\n\n`;
  for (const comp of c.components) {
    if (comp.type === 'kpi_group') {
      for (const item of comp.items) {
        md += `- **${item.title}**: ${item.value}\n`;
      }
      md += '\n';
    } else if (comp.type === 'text') {
      md += comp.content.replace(/<[^>]+>/g, '') + '\n\n';
    } else if (comp.type === 'table') {
      md += '| ' + comp.columns.map(c => c.name).join(' | ') + ' |\n';
      md += '| ' + comp.columns.map(() => '---').join(' | ') + ' |\n';
      for (const row of comp.rows) {
        md += '| ' + comp.columns.map(c => row[c.key] || '—').join(' | ') + ' |\n';
      }
      md += '\n';
    }
  }
  return md;
}

// ===== 模板 =====
const TEMPLATES = {
  phone: `指標\t數值
標題	P系列
首銷目標	19456
已達成	0
落後時間進度	0
上代同期	0
YOY	0
時間進度	0
首銷日期	2026-01-01
報告日期	2026-01-01
DAY	1

日期	SO	上代SO

產品	目標	已達成	YOY

渠道	目標	已達成	YOY`,
  tablet: `指標\t數值
標題	Pad系列
首銷目標	5000
已達成	0
落後時間進度	0
上代同期	0
YOY	0
時間進度	0
首銷日期	2026-01-01
報告日期	2026-01-01
DAY	1

日期	SO	上代SO

產品	目標	已達成	YOY

渠道	目標	已達成	YOY`,
  custom: '',
};

function loadTemplate(name) {
  document.getElementById('tsvInput').value = TEMPLATES[name] || '';
  document.getElementById('productTitle').value = name === 'phone' ? 'P12系列' : name === 'tablet' ? 'Pad系列' : '';
  showSection('generator');
  // 切回貼上 tab
  document.querySelectorAll('.tabs .tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelector('.tabs .tab').classList.add('active');
  document.getElementById('tab-paste').classList.add('active');
  showToast(`✅ ${name === 'phone' ? '手機' : name === 'tablet' ? '平板' : '空白'}模板已載入`);
}

// ===== Feishu 鏈接拉取 =====
function parseFeishuUrl(url) {
  url = url.trim();
  // 支持格式：
  // https://xiaomi.feishu.cn/sheets/xxxxxx?sheet=yyyyy
  // https://xiaomi.feishu.cn/wiki/xxxxxx
  // https://xiaomi.feishu.cn/base/xxxxxx?table=tblxxxx
  // https://xiaomi.feishu.cn/docx/xxxxxx
  const m = url.match(/feishu\.cn\/(sheets|wiki|base|docx|minutes)\/([A-Za-z0-9_-]+)/);
  if (!m) return null;
  return { type: m[1], token: m[2] };
}

async function fetchFeishu() {
  const url = document.getElementById('feishuUrl').value.trim();
  const statusEl = document.getElementById('feishuStatus');
  const fetchBtn = document.getElementById('fetchBtn');

  if (!url) {
    statusEl.className = 'feishu-status error';
    statusEl.textContent = '❌ 請輸入飛書鏈接';
    return;
  }

  const info = parseFeishuUrl(url);
  if (!info) {
    statusEl.className = 'feishu-status error';
    statusEl.textContent = '❌ 無法識別鏈接格式，請確認是飛書表格鏈接';
    return;
  }

  statusEl.className = 'feishu-status loading';
  statusEl.innerHTML = '<span class="spinner"></span>正在拉取數據...';
  fetchBtn.disabled = true;

  try {
    // 用公開導出接口嘗試拉取
    let data = null;

    if (info.type === 'sheets') {
      data = await fetchSheetsData(info.token);
    } else if (info.type === 'wiki') {
      // Wiki 需要先解析 node token 得到實際 doc token
      data = await fetchWikiData(info.token);
    } else if (info.type === 'base') {
      statusEl.className = 'feishu-status error';
      statusEl.innerHTML = '⚠️ 多維表格暫不支持自動拉取。<br>請在飛書中選中數據 → Ctrl+C → 粘貼到下方文本框。';
      fetchBtn.disabled = false;
      return;
    } else {
      statusEl.className = 'feishu-status error';
      statusEl.innerHTML = '⚠️ 該類型文檔暫不支持自動拉取。<br>請在飛書中選中數據 → Ctrl+C → 粘貼到下方文本框。';
      fetchBtn.disabled = false;
      return;
    }

    if (data && data.trim()) {
      document.getElementById('feishuTsv').value = data;
      statusEl.className = 'feishu-status success';
      statusEl.textContent = '✅ 數據已拉取！點擊下方「用粘貼的數據生成日報」繼續。';
    } else {
      throw new Error('返回數據為空');
    }
  } catch (e) {
    console.error('Fetch error:', e);
    statusEl.className = 'feishu-status error';
    statusEl.innerHTML = `⚠️ 自動拉取失敗：${e.message}<br>請在飛書中選中數據 → Ctrl+C → 粘貼到下方文本框。`;
  } finally {
    fetchBtn.disabled = false;
  }
}

async function fetchSheetsData(token) {
  // 嘗試用公開導出接口
  const exportUrl = `https://open.feishu.cn/open-apis/sheets/v2/export/${token}`;
  // 由於 CORS 限制，直接調用會失敗
  // 改用提示用戶手動粘貼
  throw new Error('飛書表格需要授權才能訪問，請手動粘貼數據');
}

async function fetchWikiData(token) {
  throw new Error('飛書 Wiki 需要授權才能訪問，請手動粘貼數據');
}

function useFeishuTsv() {
  const tsv = document.getElementById('feishuTsv').value.trim();
  if (!tsv) {
    showToast('❌ 請先粘貼數據');
    return;
  }
  // 把飛書 TSV 複製到主輸入框
  document.getElementById('tsvInput').value = tsv;
  generateReport();
}
