const API = '/api';
const D = {};
const loaded = {};

// ═══════════════ Plotly 全局美化 ═══════════════
(function(){
  if (typeof Plotly === 'undefined') return;
  // 丰富调色板
  Plotly.COLORS = {
    palette: ['#4F6BED','#EF4444','#10B981','#F59E0B','#8B5CF6','#EC4899','#06B6D4','#F97316','#84CC16','#6366F1','#14B8A6','#E11D48'],
    blue: ['#DBEAFE','#93C5FD','#60A5FA','#3B82F6','#2563EB','#4F6BED'],
    red:  ['#FEE2E2','#FCA5A5','#F87171','#EF4444','#DC2626','#E0556A'],
    green:['#D1FAE5','#6EE7B7','#34D399','#10B981','#059669','#2DA87A'],
    warm: ['#FEF3C7','#FDE68A','#FBBF24','#F59E0B','#D97706','#D4853E'],
    purple:['#EDE9FE','#C4B5FD','#A78BFA','#8B5CF6','#7C3AED','#7C5CED'],
    heatmap: [[0,'#FEF3C7'],[0.25,'#FDE68A'],[0.5,'#FB923C'],[0.75,'#EF4444'],[1,'#7C3AED']],
  };
  // 全局默认布局
  Plotly.defaults = Plotly.defaults || {};
  var O = Plotly.defaults;
  O.font = O.font || {};
  O.font.family = '"Inter","PingFang SC","Microsoft YaHei",system-ui,sans-serif';
  O.font.color = '#6B7280';
  O.plot_bgcolor = '#fff';
  O.paper_bgcolor = '#fff';
  O.xaxis = O.xaxis || {}; O.xaxis.gridcolor = '#F3F4F6';
  O.yaxis = O.yaxis || {}; O.yaxis.gridcolor = '#F3F4F6';
  O.colorway = Plotly.COLORS.palette;
})();


async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
}

// ═══ 通用 Plotly layout ═══

// ═══════════════ Toast 通知 ═══════════════
function showToast(msg, type) {
  type = type || 'info';
  var container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div'); container.id = 'toast-container';
    document.body.appendChild(container);
  }
  var toast = document.createElement('div');
  toast.className = 'toast toast-' + type;
  toast.textContent = msg;
  toast.addEventListener('click', function() { this.classList.add('hide'); setTimeout(function() { toast.remove(); }, 400); });
  container.appendChild(toast);
  requestAnimationFrame(function() { toast.classList.add('show'); });
  setTimeout(function() { toast.classList.add('hide'); setTimeout(function() { toast.remove(); }, 400); }, 5000);
}

// ═══════════════ 数字滚动动画 ═══════════════
function animateNumbers(selector) {
  var els = document.querySelectorAll(selector);
  if (!els.length) return;
  els.forEach(function(el) {
    var target = parseFloat(el.getAttribute('data-target'));
    if (isNaN(target)) return;
    var prefix = el.getAttribute('data-prefix') || '';
    var suffix = el.getAttribute('data-suffix') || '';
    var isInt = el.getAttribute('data-int') !== 'false';
    var duration = 800, start = performance.now(), from = 0;
    function step(now) {
      var elapsed = now - start;
      var progress = Math.min(elapsed / duration, 1);
      // Cubic ease-out
      var eased = 1 - Math.pow(1 - progress, 3);
      var current = from + (target - from) * eased;
      el.textContent = prefix + (isInt ? Math.round(current).toLocaleString() : current.toFixed(1)) + suffix;
      if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  });
}

const BASE_MARGIN = { t:40,b:55,l:70,r:30 };
function LAYOUT(title, opts){
  opts = opts || {};
  var t = title ? { text:title, font:{size:14,color:'#1F2937',family:'var(--font)'} } : {};
  return Object.assign({
    margin: { t:44,b:60,l:74,r:36 },
    title: t,
    yaxis: { automargin:true, gridcolor:'#F3F4F6', zerolinecolor:'#E5E7EB', zerolinewidth:1 },
    xaxis: { automargin:true, gridcolor:'#F3F4F6', tickangle:-30 },
    plot_bgcolor:'#fff', paper_bgcolor:'#fff',
    font: { color:'#6B7280', family:'"Inter","PingFang SC",system-ui' },
    hovermode:'closest', hoverlabel:{bgcolor:'#fff',bordercolor:'#E5E7EB',font:{size:12,color:'#1F2937'}},
    modebar:{bgcolor:'transparent',color:'#9CA3AF',activecolor:'#4F6BED'},
  }, opts);
}

// ═══════════════ 预算滑块 ═══════════════
function getBudget() {
  const s = document.getElementById('budget-slider');
  return s ? parseInt(s.value) || 1500 : 1500;
}

function _updateBudgetLine(divId, shapeIdx, annIdx, budget) {
  // Live-update budget line shape + annotation in a Plotly chart, if rendered
  try {
    const el = document.getElementById(divId);
    if (!el || !el._fullLayout) return;  // not rendered yet
    const layout = { [`shapes[${shapeIdx}].y0`]: budget, [`shapes[${shapeIdx}].y1`]: budget };
    if (annIdx >= 0) {
      layout[`annotations[${annIdx}].y`] = budget;
      layout[`annotations[${annIdx}].text`] = `月预算 ¥${budget.toLocaleString()}`;
    }
    Plotly.relayout(el, layout);
  } catch (_) { /* chart not rendered — next tab open will use new budget */ }
}

function onBudgetChange() {
  const val = getBudget();
  document.getElementById('budget-label').innerHTML = `¥${val.toLocaleString()}`;

  // 1) Overview expense chart — live update bar colors + budget line
  try {
    const ovEl = document.getElementById('ov-expense');
    if (ovEl && ovEl._fullLayout) {
      const xData = ovEl._fullData[0]?.x || [];
      const yData = ovEl._fullData[0]?.y || [];
      const markerColors = yData.map(function(v){ return v > val ? '#EF4444' : '#4F6BED'; });
      Plotly.restyle(ovEl, { 'marker.color': [markerColors] });
    }
  } catch (_) {}
  _updateBudgetLine('ov-expense', 0, -1, val);

  // 2) Forecast animation chart — live update budget line + annotation
  _updateBudgetLine('fc-anim-plot', 0, 0, val);

  // 3) Invalidate caches so full re-render uses new budget on next tab switch
  loaded['overview'] = false;
  loaded['forecast'] = false;
}

// ═══════════════ 指标说明弹窗 ═══════════════
function showModal(title, bodyHtml) {
  let modal = document.getElementById('metric-modal');
  if (!modal) {
    modal = document.createElement('div'); modal.id = 'metric-modal';
    modal.className = 'metric-modal';
    modal.innerHTML = `<div class="modal-content"><button class="close-btn" onclick="this.closest('.metric-modal').classList.remove('show')">×</button><h3></h3><div class="body"></div></div>`;
    modal.addEventListener('click', e => { if (e.target === modal) modal.classList.remove('show'); });
    document.body.appendChild(modal);
  }
  modal.querySelector('h3').textContent = title;
  modal.querySelector('.body').innerHTML = bodyHtml;
  modal.classList.add('show');
}

function showHealthModal() {
  const h = D.health_score || {}, f = D.financial || {};
  const sc = h.sub_scores || {};
  showModal('🩺 财务健康评分 · 计算方式', `
    <p>综合评分由以下四项<b>加权</b>计算 (满分 100)：</p>
    <p><b>储蓄率</b> (权重 35%) — 当前 ${(h.saving_rate*100).toFixed(1)}%，得分 <b>${sc.saving||'—'}</b></p>
    <p><b>恩格尔系数</b> (权重 25%) — 当前 ${(h.engel*100).toFixed(1)}%，得分 <b>${sc.engel||'—'}</b></p>
    <p><b>预算偏差率</b> (权重 25%) — 月度支出与月预算的平均偏差，得分 <b>${sc.budget||'—'}</b></p>
    <p><b>支出波动性</b> (权重 15%) — 月度支出的变异系数 (CV)，得分 <b>${sc.cv||'—'}</b></p>
    <p style="color:var(--muted2);font-size:11px;">评分标准：≥80 优秀 · 60-80 良好 · 40-60 一般 · <40 需要关注</p>
  `);
}

function showEngelModal() {
  const f = D.financial || {};
  const food = (f.total_expense||0) * (f.engel||0);
  showModal('🏥 恩格尔系数 · 说明', `
    <p><b>公式：餐饮支出 ÷ 总支出 × 100%</b></p>
    <p>当前值：<b style="color:${f.engel<0.4?'#2DA87A':f.engel<0.5?'#D4853E':'#E0556A'}">${(f.engel*100).toFixed(1)}%</b></p>
    <p>餐饮支出：<b>¥${food.toLocaleString()}</b> · 总支出：<b>¥${(f.total_expense||0).toLocaleString()}</b></p>
    <p>含义：花在"吃"上的钱占总支出的比例。数值越低说明用于基础饮食的比例越少，可自由支配的资金越多。</p>
    <p style="color:var(--muted2);font-size:11px;">参考线：&lt;40% 富裕 · 40-50% 小康 · 50-59% 温饱 · &gt;59% 贫困</p>
  `);
}

function showSavingModal() {
  const f = D.financial || {};
  showModal('💰 储蓄率 · 说明', `
    <p><b>公式：(总收入 - 总支出) ÷ 总收入 × 100%</b></p>
    <p>当前值：<b style="color:${f.saving_rate>=0.2?'#2DA87A':'#D4853E'}">${(f.saving_rate*100).toFixed(1)}%</b></p>
    <p>总收入：<b>¥${(f.total_income||0).toLocaleString()}</b> · 净结余：<b>¥${(f.net||0).toLocaleString()}</b></p>
    <p>含义：赚到的钱中有多少真正存了下来。是财务健康最重要的单一指标——储蓄率越高，抗风险能力越强。</p>
    <p style="color:var(--muted2);font-size:11px;">参考线：&gt;30% 优秀 · 20-30% 良好 · 10-20% 一般 · &lt;10% 需要关注</p>
  `);
}

async function fetchMessages() {
  try {
    const msgs = await fetchJSON(`${API}/system-messages`);
    const el = document.getElementById('msg-list');
    if (!el || !msgs.length) return;
    el.innerHTML = msgs.map(function(m) {
      var cls = m.level === 'ERROR' ? 'error' : m.level === 'WARN' ? 'warn' : 'info';
      var icon = m.level === 'ERROR' ? '✕' : m.level === 'WARN' ? '⚠' : '·';
      return '<div class="msg-item ' + cls + '"><span class="msg-time">' + (m.time || '') + '</span><span class="msg-dot">' + icon + '</span><span>' + (m.message || '') + '</span></div>';
    }).join('');
  } catch(e) {}
}

// ═══════════════ 心跳保活 ═══════════════
setInterval(function() {
  fetch('/api/heartbeat', { method:'POST' }).catch(function(){});
}, 8000);

// ═══════════════ 启动 ═══════════════
async function init() {
  try {
    const [summary, ym] = await Promise.all([
      fetchJSON(`${API}/summary`),
      fetchJSON(`${API}/year-months`),
    ]);
    Object.assign(D, summary, ym);
    D.year_months_sorted = ym.year_months;
    document.getElementById('date-range').textContent = D.date_range || '—';
    document.getElementById('clear-data-btn').style.display = '';
    renderSummaryCards();
    fetchMessages();
    loadDashboard();
  } catch(e) {
    document.getElementById('summary-cards').innerHTML =
      `<div class="spinner" style="color:#E0556A;">⚠️ 无法连接后端<br>请先启动: python mypayment_api.py<br><small>${e}</small></div>`;
  }
}

function renderSummaryCards() {
  const f = D.financial || {}, h = D.health_score || {};
  const items = [
    { id:'income',   target: f.total_income||0, prefix:'¥', isInt:true,  l: '总收入',         c: 'var(--success)', click: null },
    { id:'expense',  target: f.total_expense||0, prefix:'¥', isInt:true,  l: '总支出',         c: 'var(--danger)',  click: null },
    { id:'net',      target: f.net||0, prefix:'¥', isInt:true,            l: '净结余',         c: (f.net||0)>=0?'var(--success)':'var(--danger)', click: null },
    { id:'health',   target: h.total_score||0, suffix:' 分', isInt:true,  l: '财务健康评分 · 点击查看计算方式',   c: h.total_score>=80?'var(--success)':h.total_score>=60?'var(--warning)':'var(--danger)', click: showHealthModal },
    { id:'engel',    target: ((f.engel||0)*100), suffix:'%', isInt:false, l: '恩格尔系数 · 点击查看说明', c: f.engel<0.4?'var(--success)':f.engel<0.5?'var(--warning)':'var(--danger)', click: showEngelModal },
    { id:'saving',   target: ((f.saving_rate||0)*100), suffix:'%', isInt:false, l: '储蓄率 · 点击查看说明',         c: f.saving_rate>=0.2?'var(--success)':'var(--warning)', click: showSavingModal },
  ];
  document.getElementById('summary-cards').innerHTML = items.map(function(c) {
    var formatted = c.prefix ? c.prefix + (c.isInt ? Math.round(c.target).toLocaleString() : c.target.toFixed(1)) + (c.suffix || '') : String(c.target);
    return '<div class="stat-card accent-' + c.id + (c.click?' clickable':'') + '"' + (c.click ? ' onclick="' + c.click.name + '()"' : '') + '>' +
      '<div class="sc-value" style="color:' + c.c + '" data-target="' + c.target + '" data-prefix="' + (c.prefix || '') + '" data-suffix="' + (c.suffix || '') + '" data-int="' + c.isInt + '">' + formatted + '</div>' +
      '<div class="sc-label">' + c.l + '</div></div>';
  }).join('');
  // 启动数字动画
  setTimeout(function() { animateNumbers('.stat-card .sc-value'); }, 100);
}


// ═══════════════ 选项卡 ═══════════════
const tabLoaders = {
   trend: loadTrend, drill: loadDrill,
  compare: loadCompare, alert: loadAlert, forecast: loadForecastTab,
  detail: loadDetail, social: loadSocial, search: loadSearch,
};

// Page switching (top nav)
document.querySelectorAll('.nav-link').forEach(function(link) {
  link.addEventListener('click', function() {
    document.querySelectorAll('.nav-link').forEach(function(l) { l.classList.remove('active'); l.setAttribute('aria-selected','false'); });
    this.classList.add('active'); this.setAttribute('aria-selected','true');
    document.querySelectorAll('.page').forEach(function(p) { p.classList.remove('active'); });
    document.getElementById('page-' + this.dataset.page).classList.add('active');
    if (this.dataset.page === 'analysis' && !loaded['analysis-init']) {
      loaded['analysis-init'] = true;
      var activeTab = document.querySelector('.analysis-tab.active');
      if (activeTab) activeTab.click();
    }
  });
});

// Analysis sub-tabs
var atabs = document.getElementById('analysis-tabs'); if (atabs) atabs.addEventListener('click', function(e) {
  var tab = e.target.closest('.analysis-tab');
  if (!tab) return;
  document.querySelectorAll('.analysis-tab').forEach(function(t) { t.classList.remove('active'); t.setAttribute('aria-selected','false'); });
  tab.classList.add('active'); tab.setAttribute('aria-selected','true');
  var name = tab.dataset.atab;
  document.querySelectorAll('.analysis-section').forEach(function(s) { s.classList.remove('active'); });
  var sec = document.getElementById('asec-' + name);
  if (!sec) return;
  sec.classList.add('active');
  if (!loaded[name]) { loaded[name]=true; sec.innerHTML='<div class="spinner">加载中...</div>'; tabLoaders[name](); }
  else setTimeout(function() { sec.querySelectorAll('.js-plotly-plot').forEach(function(p) { try { Plotly.Plots.resize(p); } catch(_){} }); }, 150);
});

// ═══════════════ 📊 总览 ═══════════════
async function loadDashboard() {
  try {
    var expData, catData;
    var results = await Promise.all([
      fetchJSON(API + '/monthly-expense'),
      fetchJSON(API + '/categories'),
    ]);
    expData = results[0]; catData = results[1];
    var months = expData.months||[], vals = expData.values||[];
    var amt = catData.amount||{}, labels = Object.keys(amt), values = Object.values(amt);

    Plotly.newPlot('ov-expense', [{
      x: months, y: vals, type: 'bar', name: '支出',
      marker: { color: vals.map(function(v){ return v>getBudget()?'#EF4444':'#4F6BED'; }), line:{width:0} },
      text: vals.map(function(v){ return '¥'+(v||0).toFixed(0); }), textposition: 'outside', textfont: { size:9 },
    }], LAYOUT('', {
      shapes: [{ type:'line', x0:months[0], x1:months[months.length-1], y0:getBudget(), y1:getBudget(),
         line:{ color:'#EF4444', dash:'dash', width:1.2 } }],
      xaxis: { tickangle:-45, automargin:true },
    }), { responsive:true });

    Plotly.newPlot('ov-cat-pie', [{
      labels: labels, values: values, type: 'pie', hole: 0.5,
      marker: { colors: Plotly.COLORS ? Plotly.COLORS.palette.slice(0,10) : ['#4F6BED','#EF4444','#10B981','#F59E0B','#8B5CF6','#EC4899','#06B6D4','#F97316','#6366F1','#14B8A6'] },
      textinfo: 'label+percent', textfont: { size:11 },
    }], { margin:{t:10,b:10,l:10,r:10}, legend:{font:{size:11}} }, { responsive:true });

    // Asset trend — fetch all-flow data (收入+支出+不计收支)
    fetchJSON(API + '/asset-trend-full').then(function(at) {
      var months2 = at.months || [];
      // Total assets (含转账/充值/提现)
      var totalFlow = at.total_flow || [];
      // Operating flow only (纯收入-纯支出)
      var opFlow = at.op_flow || [];
      var cum = 0, cum_op = 0;
      var total = totalFlow.map(function(v){ cum += v; return cum; });
      var op = opFlow.map(function(v){ cum_op += v; return cum_op; });

      Plotly.newPlot('ov-assets', [
        { x: months2, y: total, type: 'scatter', mode: 'lines+markers',
          line: { color:'#4F6BED', width:2.5 }, marker: { size:4, color:'#4F6BED' },
          fill: 'tozeroy', fillcolor: 'rgba(79,107,237,0.10)',
          name: '微信账户余额 (含充值/提现/转账)' },
        { x: months2, y: op, type: 'scatter', mode: 'lines',
          line: { color:'#9CA3AF', width:1.2, dash:'dash' },
          name: '经营现金流' }
      ], LAYOUT('', { xaxis:{ tickangle:-45 },
        legend: { orientation:'h', y:1.08, font:{size:10} },
        shapes: [{ type:'line', x0:months2[0], x1:months2[months2.length-1], y0:0, y1:0, line:{ color:'#E5E7EB', width:1 } }],
    }), { responsive:true });
    });

    // Yearly top3
    loadYearlyTop3();

  } catch(e) { document.getElementById('page-dashboard').innerHTML = '<div class="spinner" style="color:#EF4444;">⚠️ 加载失败: '+e+'</div>'; }
}


// ═══════════════ 📈 趋势 ═══════════════
async function loadTrend() {
  const el = document.getElementById('asec-trend');
  try {
    const cats = await fetchJSON(`${API}/categories`);
    const ct = cats.monthly_trend || {};
    const topCats = ct.top_categories || [];
    const amount = ct.amount || [];
    var colors = ['#4F6BED','#EF4444','#10B981','#F59E0B','#8B5CF6','#EC4899','#06B6D4','#F97316','#6366F1','#84CC16'];

    el.innerHTML = `
      <div class="chart-row full">
<div class="chart-box">
  <h3>消费分类月度趋势 — 堆叠面积</h3>
  <div class="hint">各分类面积叠加 = 当月总支出。面积变化反映消费结构变迁——例如"餐饮"面积增大说明恩格尔系数上升。</div>
  <div id="tr-stack" class="plot-lg"></div>
</div>
      </div>
      <div class="chart-row">
<div class="chart-box">
  <h3>各时段消费热力图</h3>
  <div class="hint">横轴 = 小时 (0~23h)，纵轴 = 星期。颜色越深消费越高。可发现"周末晚餐时段"等消费高峰。</div>
  <div id="tr-heat" class="plot-md"></div>
</div>
<div class="chart-box">
  <h3>各分类独立走势</h3>
  <div class="hint">将堆叠面积拆成独立折线，便于比较各类别的上升/下降趋势。</div>
  <div id="tr-lines" class="plot-md"></div>
</div>
      </div>
      <div class="chart-row full">
<div class="chart-box">
  <h3>星期消费模式</h3>
  <div class="hint">按周一至周日汇总支出 + 平均单笔金额（紫色折线）。可判断周末消费是否显著高于工作日。</div>
  <div id="tr-weekday" class="plot-md"></div>
</div>
      </div>

    `;

    if (topCats.length) {
      Plotly.newPlot('tr-stack', topCats.map((cat,i) => ({
x: amount.map(r=>r.month), y: amount.map(r=>r[cat]||0),
name: cat, stackgroup:'one', line:{width:.3},
marker:{color:colors[i%6]},
      })), LAYOUT('', { legend:{orientation:'h',y:1.08} }), { responsive:true });

      Plotly.newPlot('tr-lines', topCats.map((cat,i) => ({
x: amount.map(r=>r.month), y: amount.map(r=>r[cat]||0),
name: cat, type:'scatter', mode:'lines+markers', marker:{size:2},
line:{color:colors[i%6],width:1.6},
      })), LAYOUT('', { legend:{orientation:'h',y:1.08} }), { responsive:true });
    }

    loadHeatmap();
    loadWeekdayTrend();

  } catch(e) { el.innerHTML = `<div class="spinner" style="color:#E0556A;">⚠️ ${e}</div>`; }
}

async function loadHeatmap() {
  try {
    const hm = await fetchJSON(`${API}/hourly-heatmap`);
    Plotly.newPlot('tr-heat', [{
      z: hm.data||[], x: (hm.hours||[]).map(h=>`${h}h`),
      y: hm.weekday_labels||[], type: 'heatmap',
      colorscale: Plotly.COLORS ? Plotly.COLORS.heatmap : [[0,'#FEF3C7'],[0.25,'#FDE68A'],[0.5,'#FB923C'],[0.75,'#EF4444'],[1,'#7C3AED']],
      hovertemplate: '%{y} %{x}<br>¥%{z:.0f}<extra></extra>', xgap:2, ygap:2,
    }], { margin:{t:10,b:30,l:80,r:30}, xaxis:{side:'top',title:'小时',dtick:1,automargin:true} }, { responsive:true });
  } catch(e) {}
}

async function loadWeekdayTrend() {
  try {
    const expData = await fetchJSON(`${API}/monthly-expense`);
    const ws = D.weekday_stats;
    if (!ws) return;
    const wdLabels = ['周一','周二','周三','周四','周五','周六','周日'];
    const wdKeys = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
    const totals = wdKeys.map(k => ws[k]?.总支出||0);
    const avgs = wdKeys.map(k => ws[k]?.平均单笔||0);

    Plotly.newPlot('tr-weekday', [
      { x: wdLabels, y: totals, type: 'bar', name: '总支出', marker:{color:'#4F6BED',line:{width:0}},
text: totals.map(v=>`¥${v?.toFixed(0)}`), textposition:'outside', textfont:{size:9} },
      { x: wdLabels, y: avgs, type: 'scatter', mode:'lines+markers', name:'笔均',
yaxis:'y2', marker:{color:'#7C5CED',size:10,symbol:'diamond'}, line:{color:'#7C5CED',width:2} },
    ], LAYOUT('', {
      legend:{orientation:'h',y:1.08},
      yaxis2:{overlaying:'y',side:'right',automargin:true,title:'笔均 (元)'},
    }), { responsive:true });
  } catch(e) {}
}

async function loadYearlyTop3() {
  var el = document.getElementById('ov-top3');
  if (!el) return;
  var sel = document.getElementById('top3-year');
  if (sel && sel.options.length <= 1) {
    var yms = D.year_months_sorted || [];
    var yrs = yms.map(function(y){ return y.slice(0,4); });
    var uniq = []; yrs.forEach(function(y){ if (uniq.indexOf(y)<0) uniq.push(y); });
    uniq.sort().reverse();
    sel.innerHTML = '<option value=>全部年份</option><option value="'+uniq[uniq.length-1]+'">'+uniq[uniq.length-1]+'年</option>';
    if (uniq.length>1) uniq.slice(0,-1).reverse().forEach(function(y){ sel.innerHTML += '<option value="'+y+'">'+y+'年</option>'; });
    sel.value = uniq[uniq.length-1] || '';
  }
  var selectedYear = sel ? (sel.value || '') : '';
  try {
    var t3 = await fetchJSON(API + '/yearly-top3');
    el.innerHTML = '';

    var configs = [
      {k:'top3_income',  icon:'📈', label:'收入 Top 3',  col:'收入',   color:'#10B981'},
      {k:'top3_expense', icon:'📉', label:'支出 Top 3',  col:'支出',   color:'#EF4444'},
      {k:'top3_balance', icon:'💰', label:'结余 Top 3',  col:'结余',   color:'#4F6BED'},
      {k:'top3_trans',   icon:'📊', label:'交易 Top 3',  col:'交易次数', color:'#8B5CF6'},
    ];

    configs.forEach(function(cfg,i){
      var box = document.createElement('div');
      box.style.cssText = 'width:49%;display:inline-block;vertical-align:top;margin-bottom:10px;';

      var hdr = document.createElement('div');
      hdr.style.cssText = 'display:flex;align-items:center;gap:6px;margin-bottom:6px;font-size:12px;font-weight:700;color:#1F2937;';
      hdr.innerHTML = '<span style="font-size:18px;">'+cfg.icon+'</span>'+cfg.label;
      box.appendChild(hdr);

      var data = (t3[cfg.k]||[]);
      if (selectedYear) data = data.filter(function(r){ return String(r['年份'])===selectedYear; });
      if (!data.length) { box.innerHTML += '<div style="text-align:center;padding:20px;color:var(--muted2);">暂无数据</div>'; el.appendChild(box); return; }
      var sorted = data.slice().sort(function(a,b){ return (b[cfg.col]||0)-(a[cfg.col]||0); }).slice(0,3);
      var medals = ['🥇','🥈','🥉'];

      sorted.forEach(function(r,rank){
        var card = document.createElement('div');
        var rankColor = rank===0 ? '#F59E0B' : rank===1 ? '#9CA3AF' : '#D4A574';
        card.style.cssText = 'display:flex;align-items:center;gap:10px;padding:7px 10px;margin:3px 0;background:#F9FAFB;border-radius:8px;border-left:3px solid '+cfg.color+';font-size:11px;';
        var val = cfg.col==='交易次数' ? (r[cfg.col]||0)+' 笔' : '¥'+(r[cfg.col]||0).toLocaleString();
        card.innerHTML = '<span style="font-size:18px;">'+medals[rank]+'</span>' +
          '<span style="flex:1;font-weight:600;color:#1F2937;">'+r.year_month_str+'</span>' +
          '<span style="font-weight:700;color:'+cfg.color+';font-family:monospace;">'+val+'</span>';
        box.appendChild(card);
      });
      el.appendChild(box);
    });
  } catch(e) { console.error('Yearly top3:', e); }
}

async function loadDrill() {
  const el = document.getElementById('asec-drill');
  const years = D.year_months_sorted ? [...new Set(D.year_months_sorted.map(y=>y.slice(0,4)))] : [];
  el.innerHTML = `
    <div class="controls">
      <span style="font-size:13px;color:var(--muted);font-weight:600;">层级:</span>
      <select id="drill-level" onchange="onDrillLevelChange()">
<option value="all">全部数据</option><option value="year">按年</option>
<option value="quarter">按季度</option><option value="month">按月</option>
      </select>
      <select id="drill-year" style="display:none" onchange="onDrillParamChange()">
<option value="">选择年份</option>
${years.map(y=>`<option value="${y}">${y}年</option>`).join('')}
      </select>
      <select id="drill-quarter" style="display:none" onchange="onDrillParamChange()">
<option value="">选择季度</option>
<option value="1">Q1(1-3月)</option><option value="2">Q2(4-6月)</option>
<option value="3">Q3(7-9月)</option><option value="4">Q4(10-12月)</option>
      </select>
      <select id="drill-month" style="display:none" onchange="onDrillParamChange()">
<option value="">选择月份</option>
      </select>
    </div>
    <div id="drill-content"><div class="spinner">加载中...</div></div>
  `;
  refreshDrillMulti();
}
function onDrillLevelChange() {
  const lv = document.getElementById('drill-level')?.value;
  document.getElementById('drill-year').style.display = (lv==='year'||lv==='quarter'||lv==='month')?'':'none';
  // quarter 选择器仅在 quarter 级别显示，month 级别不显示（直接选月份）
  document.getElementById('drill-quarter').style.display = (lv==='quarter')?'':'none';
  document.getElementById('drill-month').style.display = (lv==='month')?'':'none';
  // 切换层级时清空筛选器
  if (lv === 'all') document.getElementById('drill-year').value = '';
  if (lv !== 'quarter') document.getElementById('drill-quarter').value = '';
  if (lv !== 'month') document.getElementById('drill-month').value = '';
  // 选季度或月度时，自动选中最近年份
  if ((lv==='quarter'||lv==='month') && document.getElementById('drill-year')?.value === '') {
    const yearSel = document.getElementById('drill-year');
    if (yearSel && yearSel.options.length > 1) yearSel.value = yearSel.options[yearSel.options.length-1].value;
  }
  _updateDrillMonths();
  refreshDrillMulti();
}
function onDrillParamChange() {
  // 注意：_updateDrillMonths 会重建下拉框，必须在 refreshDrillMulti 之前调用
  // 但 refreshDrillMulti 需要读到选中值 → 先保存再恢复
  const monSel = document.getElementById('drill-month');
  const savedMonth = monSel?.value || '';
  _updateDrillMonths();
  if (savedMonth && monSel) {
    // 恢复选中值（如果重建后的选项里有它）
    for (let i = 0; i < monSel.options.length; i++) {
      if (monSel.options[i].value === savedMonth) { monSel.value = savedMonth; break; }
    }
  }
  refreshDrillMulti();
}
function _updateDrillMonths() {
  const lv = document.getElementById('drill-level')?.value;
  const monSel = document.getElementById('drill-month');
  if (!monSel) return;
  // 保存当前选中值
  const saved = monSel.value;
  monSel.innerHTML = '<option value="">选择月份</option>';
  if (lv !== 'month') return;
  // month 级别：显示全年 12 个月
  for (let m = 1; m <= 12; m++) {
    monSel.innerHTML += '<option value="' + m + '">' + m + '月</option>';
  }
  // 恢复选中值
  if (saved) monSel.value = saved;
}
async function refreshDrillMulti() {
  const lv = document.getElementById('drill-level')?.value||'all';
  const yr = document.getElementById('drill-year')?.value||'';
  const q  = document.getElementById('drill-quarter')?.value||'';
  const mo = document.getElementById('drill-month')?.value||'';
  let p = `level=${lv}`; if(yr)p+=`&year=${yr}`;
  // quarter 仅在 quarter 级别传入，month 级别通过 month 参数直接筛选
  if(lv==='quarter' && q)p+=`&quarter=${q}`;
  if(lv==='month' && mo)p+=`&month=${mo}`;
  document.getElementById('drill-content').innerHTML = '<div class="spinner">加载中...</div>';
  try { renderDrillResult(await fetchJSON(`${API}/drill-level?${p}`)); }
  catch(e) { document.getElementById('drill-content').innerHTML = `<div class="spinner" style="color:#E0556A;">${e}</div>`; }
}

function renderDrillResult(d) {
  const groups = d.next_groups||[];
  const hasDaily = Object.keys(d.daily||{}).length > 0;
  document.getElementById('drill-content').innerHTML = `
    <div class="chart-row">
      <div class="chart-box">
<h3>「${d.label}」总览</h3>
<div class="hint">${d.next_level ? `点击下方柱状图条块可钻取到 <b>${d.next_level}</b> 级别。` : '已到最小粒度，展示每日支出明细。'}</div>
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:10px 0 16px;">
  <div class="card"><div class="value" style="font-size:20px;">¥${(d.expense||0).toLocaleString()}</div><div class="label">支出</div></div>
  <div class="card"><div class="value" style="font-size:20px;color:var(--success);">¥${(d.income||0).toLocaleString()}</div><div class="label">收入</div></div>
  <div class="card"><div class="value" style="font-size:20px;">${d.count||0}笔</div><div class="label">交易</div></div>
  <div class="card"><div class="value" style="font-size:20px;color:var(--purple);">¥${(d.avg||0).toLocaleString()}</div><div class="label">笔均</div></div>
</div>
${groups.length?`<div id="dr-bars" style="height:${Math.max(220,groups.length*40)}px;width:100%"></div>`:''}
      </div>
      <div class="chart-box"><h3>消费分类</h3><div id="dr-pie" class="plot-lg"></div></div>
    </div>
    <div class="chart-row">
      <div class="chart-box"><h3>Top 8 商户</h3><div id="dr-top5" class="plot-md"></div></div>
      <div class="chart-box"><h3>${hasDaily?'每日支出':'层级导航'}</h3><div id="dr-daily" class="plot-md"></div></div>
    </div>
  `;
  if (groups.length) {
    const cm = {year:'#4F6BED', quarter:'#F59E0B', month:'#10B981'};
    const curLevel = d.next_level || d.level;  // month 级别 next_level 为 None，回退到 d.level
    const labelFn = curLevel === 'month' ? k => k + '月' :
                    curLevel === 'quarter' ? k => 'Q' + k :
                    curLevel === 'year' ? k => k + '年' : k => k;
    Plotly.newPlot('dr-bars', [{
      x: groups.map(g=>labelFn(g.key!=null?g.key:'全部')), y: groups.map(g=>g.total),
      type:'bar', marker:{color:cm[curLevel]||'#4F6BED',line:{width:0}},
      text: groups.map(g=>`¥${g.total?.toFixed(0)}`), textposition:'outside', textfont:{size:9},
    }], LAYOUT(''), { responsive:true });
    document.getElementById('dr-bars').on('plotly_click', evt => {
      const key = evt.points[0].x, nl = d.next_level;
      if(nl==='year'){document.getElementById('drill-level').value='year';document.getElementById('drill-year').value=key;document.getElementById('drill-year').style.display='';onDrillLevelChange();}
      else if(nl==='quarter'){document.getElementById('drill-level').value='quarter';document.getElementById('drill-quarter').value=key;document.getElementById('drill-quarter').style.display='';onDrillLevelChange();}
      else if(nl==='month'){document.getElementById('drill-level').value='month';document.getElementById('drill-month').value=key;document.getElementById('drill-month').style.display='';onDrillLevelChange();}
      // 已在 month 级别：点击某个月份柱子 → 直接选该月刷新
      else if(d.level==='month'){document.getElementById('drill-month').value=key;onDrillParamChange();}
    });
  }
  const cats = Object.entries(d.categories||{}).sort((a,b)=>b[1]-a[1]);
  Plotly.newPlot('dr-pie', [{
    labels: cats.map(x=>x[0]), values: cats.map(x=>x[1]), type:'pie', hole:.5, textfont:{size:11},
  }], { margin:{t:10,b:10,l:10,r:10} }, { responsive:true });
  const t8 = Object.entries(d.top5||{}).sort((a,b)=>a[1]-b[1]).slice(-8);
  Plotly.newPlot('dr-top5', [{
    y: t8.map(x=>x[0]), x: t8.map(x=>x[1]), type:'bar', orientation:'h',
    marker:{color:'#4F6BED',line:{width:0}},
    text: t8.map(x=>`¥${x[1].toFixed(0)}`), textposition:'outside', textfont:{size:9},
  }], { margin:{t:10,b:25,l:170,r:70}, xaxis:{automargin:true}, yaxis:{automargin:true} }, { responsive:true });
  if (hasDaily) {
    const days = Object.keys(d.daily).map(Number).sort((a,b)=>a-b);
    Plotly.newPlot('dr-daily', [{
      x: days, y: days.map(dd=>d.daily[dd]||0), type:'scatter', mode:'lines+markers',
      fill:'tozeroy', fillcolor:'rgba(79,107,237,0.06)', line:{color:'#4F6BED',width:2}, marker:{size:4},
    }], LAYOUT(''), { responsive:true });
  } else if (d.next_level) {
    document.getElementById('dr-daily').innerHTML = `<div style="text-align:center;padding:60px 20px;color:var(--muted2);line-height:2;">
      当前: <b>${d.label}</b><br>点击柱状图钻取<br><br>
      <button onclick="document.getElementById('drill-level').value='${d.next_level}';onDrillLevelChange();">到 ${d.next_level} 视图</button>
    </div>`;
  }
}

// ═══════════════ 🆚 对比 ═══════════════
async function loadCompare() {
  const el = document.getElementById('asec-compare');
  const yms = D.year_months_sorted||[];
  const a=yms[yms.length-1]||'', b=yms[Math.max(0,yms.length-7)]||'';
  el.innerHTML = `
    <div class="controls">
      <select id="comp-a">${yms.map(y=>`<option value="${y}" ${y===a?'selected':''}>${y}</option>`).join('')}</select>
      <span style="font-size:18px;">vs</span>
      <select id="comp-b">${yms.map(y=>`<option value="${y}" ${y===b?'selected':''}>${y}</option>`).join('')}</select>
      <button onclick="refreshCompare()">对比</button>
    </div>
    <div id="comp-content"><div class="spinner">选择月份后点击对比</div></div>
  `;
  refreshCompare();
}
async function refreshCompare() {
  const a=document.getElementById('comp-a')?.value, b=document.getElementById('comp-b')?.value;
  if(!a||!b)return;
  document.getElementById('comp-content').innerHTML='<div class="spinner">对比中...</div>';
  try {
    const c=await fetchJSON(`${API}/compare-months?ym_a=${a}&ym_b=${b}`);
    const sa=c.a, sb=c.b;
    document.getElementById('comp-content').innerHTML=`
      <div class="chart-row">
<div class="chart-box"><h3>分类金额对比</h3><div class="hint">蓝 = ${a}，红 = ${b}。并排柱状图直观对比各分类差异。</div><div id="cp-cats" class="plot-lg"></div></div>
<div class="chart-box"><h3>每日走势对比</h3><div class="hint">实线 = ${a}，虚线 = ${b}。叠图比较两个月的日消费节奏。</div><div id="cp-daily" class="plot-lg"></div></div>
      </div>
      <div class="chart-row three">
<div class="chart-box"><h3>星期模式</h3><div class="hint">比较两个月份的周消费分布差异。</div><div id="cp-week" class="plot-sm"></div></div>
<div class="chart-box" style="grid-column:span 2;"><h3>差异摘要</h3><div id="cp-summary"></div></div>
      </div>
    `;
    const allCats=[...new Set([...Object.keys(sa.cats||{}),...Object.keys(sb.cats||{})])]
      .sort((x,y)=>((sb.cats[y]||0)+(sa.cats[y]||0))-((sb.cats[x]||0)+(sa.cats[x]||0))).slice(0,6);
    Plotly.newPlot('cp-cats',[
      {x:allCats,y:allCats.map(k=>sa.cats[k]||0),type:'bar',name:a,marker:{color:'#4F6BED',line:{width:0}}},
      {x:allCats,y:allCats.map(k=>sb.cats[k]||0),type:'bar',name:b,marker:{color:'#E0556A',line:{width:0}}},
    ],{barmode:'group',...LAYOUT(''),xaxis:{tickangle:-15},legend:{orientation:'h',y:1.08}},{responsive:true});
    const da=Object.entries(sa.daily||{}).sort((a,b)=>Number(a[0])-Number(b[0]));
    const db=Object.entries(sb.daily||{}).sort((a,b)=>Number(a[0])-Number(b[0]));
    Plotly.newPlot('cp-daily',[
      {x:da.map(r=>r[0]),y:da.map(r=>r[1]),type:'scatter',mode:'lines+markers',name:a,line:{color:'#4F6BED'},marker:{size:5}},
      {x:db.map(r=>r[0]),y:db.map(r=>r[1]),type:'scatter',mode:'lines+markers',name:b,line:{color:'#E0556A',dash:'dash'},marker:{size:5,symbol:'square'}},
    ],{...LAYOUT(''),legend:{orientation:'h',y:1.08}},{responsive:true});
    const wdMap=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
    const wdCN=['周一','周二','周三','周四','周五','周六','周日'];
    Plotly.newPlot('cp-week',[
      {x:wdCN,y:wdMap.map(d=>sa.week?.[d]||0),type:'scatter',mode:'lines+markers',name:a,marker:{size:7},line:{color:'#4F6BED',width:2}},
      {x:wdCN,y:wdMap.map(d=>sb.week?.[d]||0),type:'scatter',mode:'lines+markers',name:b,marker:{size:7,symbol:'square'},line:{color:'#E0556A',width:2,dash:'dash'}},
    ],{...LAYOUT(''),legend:{orientation:'h',y:1.08}},{responsive:true});
    const diff=c.diff||0;
    document.getElementById('cp-summary').innerHTML=`
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:6px;">
<div style="text-align:center;background:#fafbfc;border-radius:10px;padding:24px;border:1px solid var(--border);">
  <div style="font-size:13px;color:var(--muted2);">${a} 相比 ${b}</div>
  <div style="font-size:32px;font-weight:700;color:${diff>0?'#E0556A':'#2DA87A'};margin:10px 0;">${diff>0?'多':'少'} ¥${Math.abs(diff).toLocaleString()}</div>
  <div style="font-size:14px;color:var(--muted2);">${(c.diff_pct||0)>=0?'+':''}${(c.diff_pct||0).toFixed(1)}%</div>
</div>
<div style="background:#fafbfc;border-radius:10px;padding:20px;border:1px solid var(--border);">
  <div style="display:flex;justify-content:space-around;margin-bottom:14px;">
    <div style="text-align:center;"><b style="font-size:18px;color:#4F6BED;">${a}</b><br><span style="font-size:13px;color:var(--muted);">${sa.count}笔 / ¥${sa.avg}</span></div>
    <div style="text-align:center;"><b style="font-size:18px;color:#E0556A;">${b}</b><br><span style="font-size:13px;color:var(--muted);">${sb.count}笔 / ¥${sb.avg}</span></div>
  </div>
  <div style="font-size:12px;color:var(--muted2);border-top:1px solid var(--border);padding-top:12px;text-align:center;">
    差异最大类别<br>${(c.top_diff_categories||[]).slice(0,3).map(x=>`· ${x.name}: ${(x.diff||0)>=0?'+':''}¥${x.diff}`).join('<br>')}
  </div>
</div>
      </div>
    `;
  } catch(e) { document.getElementById('comp-content').innerHTML=`<div class="spinner" style="color:#E0556A;">${e}</div>`; }
}

// ═══════════════ 🔍 搜索 ═══════════════
async function loadSearch() {
  const el = document.getElementById('asec-search');
  el.innerHTML = `
    <div class="controls">
      <input type="text" id="search-input" placeholder="搜索商户/商品/分类/金额/日期(如2025-03)..."
     style="flex:1;min-width:300px;font-size:14px;padding:10px 16px;">
      <button id="search-btn" style="padding:10px 24px;font-size:14px;">🔍 搜索</button>
    </div>
    <div id="search-summary"></div>
    <div id="search-results"><div style="text-align:center;padding:40px;color:var(--muted2);">输入关键词开始搜索<br><span style="font-size:12px;">支持模糊匹配：商户名、商品描述、订单类型、消费分类、金额、日期（如 2025-03 搜索3月全部记录）</span></div></div>
    <div id="search-pager" style="text-align:center;margin-top:14px;"></div>
  `;
  const inp = document.getElementById('search-input');
  const btn = document.getElementById('search-btn');
  if (inp) { inp.focus(); inp.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(1); }); }
  if (btn) btn.addEventListener('click', () => doSearch(1));
}

async function doSearch(page) {
  const q = document.getElementById('search-input')?.value?.trim();
  if (!q) return;
  document.getElementById('search-results').innerHTML = '<div class="spinner">搜索中...</div>';
  document.getElementById('search-summary').innerHTML = '';
  try {
    const data = await fetchJSON(`${API}/search?q=${encodeURIComponent(q)}&page=${page}&page_size=50`);
    renderSearchResults(data, page);
  } catch(e) {
    document.getElementById('search-results').innerHTML = `<div class="spinner" style="color:#E0556A;">搜索失败: ${e}</div>`;
  }
}

function renderSearchResults(d, page) {
  const records = d.records || [];
  document.getElementById('search-summary').innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-bottom:14px;">
      <div class="card" style="padding:10px 14px;"><div class="value" style="font-size:18px;">${d.total} 条</div><div class="label">匹配记录</div></div>
      <div class="card" style="padding:10px 14px;"><div class="value" style="font-size:18px;color:#E0556A;">¥${(d.page_expense||0).toLocaleString()}</div><div class="label">本页支出</div></div>
      <div class="card" style="padding:10px 14px;"><div class="value" style="font-size:18px;color:#2DA87A;">¥${(d.page_income||0).toLocaleString()}</div><div class="label">本页收入</div></div>
      <div class="card" style="padding:10px 14px;"><div class="value" style="font-size:18px;">${d.page}/${d.total_pages}</div><div class="label">页码</div></div>
    </div>
  `;

  if (!records.length) {
    document.getElementById('search-results').innerHTML = '<div style="text-align:center;padding:40px;color:var(--muted2);">没有匹配的记录</div>';
    return;
  }

  const rows = records.map(r => {
    const cls = r.in_out === '支出' ? '#E0556A' : '#2DA87A';
    const sign = r.in_out === '支出' ? '-' : '+';
    return `<tr>
      <td style="white-space:nowrap;">${(r.time||'').slice(0,16)}</td>
      <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${r.keeper}">${r.keeper}</td>
      <td style="color:var(--muted2);font-size:11px;">${r.type}</td>
      <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${r.goods}">${r.goods}</td>
      <td style="color:var(--muted2);font-size:11px;">${r.category||''}</td>
      <td style="color:${cls};font-weight:600;text-align:right;white-space:nowrap;">${sign} ¥${(r.amount||0).toLocaleString()}</td>
    </tr>`;
  }).join('');

  document.getElementById('search-results').innerHTML = `
    <div style="overflow-x:auto;">
      <table>
<thead><tr>
  <th>时间</th><th>商户</th><th>类型</th><th>商品</th><th>分类</th><th style="text-align:right;">金额</th>
</tr></thead>
<tbody>${rows}</tbody>
      </table>
    </div>
  `;

  // Pager
  let pagerHtml = '';
  if (d.total_pages > 1) {
    const q = encodeURIComponent(document.getElementById('search-input')?.value || '');
    pagerHtml += page > 1 ? `<button onclick="doSearch(${page-1})" style="margin:0 4px;">◀ 上一页</button>` : '';
    pagerHtml += `<span style="margin:0 8px;font-size:13px;color:var(--muted);">${d.page} / ${d.total_pages}</span>`;
    pagerHtml += page < d.total_pages ? `<button onclick="doSearch(${page+1})" style="margin:0 4px;">下一页 ▶</button>` : '';
  }
  document.getElementById('search-pager').innerHTML = pagerHtml;
}

// ═══════════════ ⚠️ 预警 ═══════════════
async function loadAlert() {
  const el = document.getElementById('asec-alert');
  el.innerHTML = `
    <div class="chart-row full">
      <div class="chart-box">
        <h3>消费多样性月度趋势 — 香农熵</h3>
        <div class="hint">熵值越高 = 消费越分散在各分类中；熵值下降 = 消费越来越集中在少数类别。灰色虚线标记整体均值。</div>
        <div id="al-diversity" class="plot-lg"></div>
      </div>
    </div>
    <div class="chart-row full">
      <div class="chart-box">
        <h3>环比异常预警 — 分类月度环比涨幅 > 50%</h3>
        <div class="hint">某类别当月支出相比上月增长超过阈值（默认50%）时触发预警。可发现"餐饮突然翻倍"等异常消费模式。阈值滑块可调节灵敏度。</div>
        <div class="controls">
          <input type="range" id="mom-threshold" min="20" max="200" step="10" value="50"
                 style="width:180px;accent-color:var(--danger);" oninput="loadMomAnomalies()">
          <span style="font-size:12px;color:var(--muted);">阈值: <b id="mom-th-label" style="color:var(--danger);">50%</b></span>
        </div>
        <div id="al-mom"><div class="spinner">加载中...</div></div>
      </div>
    </div>
  `;
  loadDiversityTrend();
  loadMomAnomalies();
}

async function loadDiversityTrend() {
  try {
    const data = await fetchJSON(`${API}/diversity-trend`);
    if (!data.length) return;
    const months = data.map(r=>r.month), vals = data.map(r=>r.diversity);
    const avg = vals.reduce((a,b)=>a+b,0)/vals.length;
    Plotly.newPlot('al-diversity', [{
      x: months, y: vals, type:'scatter', mode:'lines+markers',
      line:{color:'#4F6BED',width:2.5}, marker:{size:6,color:'#4F6BED'},
      name:'多样性指数',
    }], {
      margin:{t:10,b:60,l:70,r:30}, xaxis:{tickangle:-45,automargin:true},
      yaxis:{title:'香农熵',automargin:true},
      shapes: [{type:'line',x0:months[0],x1:months[months.length-1],y0:avg,y1:avg,
                line:{color:'#a0a5b8',dash:'dash',width:1.5}}],
      annotations: [{x:months[months.length-1],y:avg,text:`均值 ${avg.toFixed(3)}`,
                     showarrow:false,font:{color:'#a0a5b8',size:10},xanchor:'right'}],
      plot_bgcolor:'#fff',paper_bgcolor:'#fff',font:{color:'#6b7084'},
    }, { responsive:true });
  } catch(e) { console.error(e); }
}

async function loadMomAnomalies() {
  const threshold = parseInt(document.getElementById('mom-threshold')?.value) || 50;
  document.getElementById('mom-th-label').textContent = threshold + '%';
  const el = document.getElementById('al-mom');
  el.innerHTML = '<div class="spinner">检测中...</div>';
  try {
    const data = await fetchJSON(`${API}/mom-anomalies?threshold=${threshold/100}`);
    if (!data.length) { el.innerHTML = '<div style="text-align:center;padding:30px;color:var(--muted2);">✅ 未发现环比异常（当前阈值下所有类别月度变化正常）</div>'; return; }
    const top15 = data.slice(0, 15);
    const rows = top15.map(r => {
      const arrow = r.mom_pct > 100 ? '🔥' : r.mom_pct > 80 ? '⚠️' : '📈';
      return `<tr>
        <td>${r.month}</td><td>${r.category}</td>
        <td style="color:#E0556A;font-weight:600;">${arrow} +${r.mom_pct}%</td>
        <td>上月 ¥${r.previous.toLocaleString()}</td>
        <td>本月 ¥${r.current.toLocaleString()}</td>
        <td style="color:#D4853E;">+¥${(r.current-r.previous).toLocaleString()}</td>
      </tr>`;
    }).join('');
    el.innerHTML = `
      <div style="overflow-x:auto;">
        <table><thead><tr><th>月份</th><th>类别</th><th>环比涨幅</th><th>上月金额</th><th>本月金额</th><th>差额</th></tr></thead><tbody>${rows}</tbody></table>
      </div>
      <div style="font-size:11px;color:var(--muted2);margin-top:8px;">共 ${data.length} 条预警 · 只显示 Top 15</div>
    `;
  } catch(e) { el.innerHTML = `<div class="spinner" style="color:#E0556A;">${e}</div>`; }
}

// ═══════════════ 🔮 预测 ═══════════════
async function loadForecastTab() {
  const el = document.getElementById('asec-forecast');
  el.innerHTML = `
    <div class="chart-row full">
      <div class="chart-box">
<h3>Prophet 未来支出预测</h3>
<div class="hint">基于 Facebook Prophet 时间序列模型，蓝色实线 = 预测中值，浅蓝区域 = 置信区间。预测假设历史消费模式延续，仅供参考。</div>
<div id="fc-plot" class="plot-lg"></div>
      </div>
    </div>
    <div class="chart-row full">
      <div class="chart-box">
<h3>支出动画</h3>
<div class="hint">逐月展开的动画折线图，直观展示支出如何随时间增长。红色标记 = 超出 ¥${getBudget().toLocaleString()} 预算的月份。</div>
<div id="fc-anim">
  <div style="text-align:center;padding:30px;color:var(--muted2);">
    <button onclick="loadExpenseAnimation()" style="font-size:14px;padding:10px 24px;">▶ 加载支出动画</button>
  </div>
</div>
      </div>
    </div>
    <div class="chart-row full">
      <div class="chart-box">
<h3>STL 时序分解</h3>
<div class="hint">
  <b>原始支出</b>：实际月度支出总金额。<br>
  <b>长期趋势</b>：过滤季节性和噪声后的长期方向——向上 = 消费升级，向下 = 消费收缩。<br>
  <b>季节性成分</b>：每年固定周期的增减量（如寒假多花、开学少花）。<br>
  <b>随机残差</b>：不可解释的异常波动——某月残差突然飙升说明有突发事件（如购机、医疗）。
</div>
<div id="fc-decomp" style="margin-top:8px;">
  <div class="spinner">加载中...</div>
</div>
      </div>
    </div>
  `;

  // Prophet
  try {
    const fc = await fetchJSON(`${API}/forecast`);
    Plotly.newPlot('fc-plot', [
      { x: fc.map(r=>r.ds), y: fc.map(r=>r.yhat), type:'scatter', mode:'lines+markers',
name:'预测值', line:{color:'#4F6BED',width:2.5}, marker:{size:7} },
      { x: fc.map(r=>r.ds), y: fc.map(r=>r.yhat_upper), type:'scatter', mode:'lines',
line:{width:0}, showlegend:false },
      { x: fc.map(r=>r.ds), y: fc.map(r=>r.yhat_lower), type:'scatter', mode:'lines',
fill:'tonexty', fillcolor:'rgba(79,107,237,0.14)', line:{width:0}, showlegend:false },
    ], LAYOUT('', { legend:{orientation:'h',y:1.08} }), { responsive:true });
  } catch(e) { document.getElementById('fc-plot').innerHTML = `<div class="spinner" style="color:#E0556A;">预测加载失败: ${e}</div>`; }

  // STL
  try {
    const dc = await fetchJSON(`${API}/decompose`);
    const titles = ['原始支出 (Observed)', '长期趋势 (Trend)', '季节性成分 (Seasonal)', '随机残差 (Residual)'];
    const keys = ['observed','trend','seasonal','resid'];
    const cols = ['#1e2235','#4F6BED','#2DA87A','#D4853E'];
    document.getElementById('fc-decomp').innerHTML = keys.map((key,i) =>
      `<div style="margin-bottom:10px;"><span style="font-size:12px;color:var(--muted);font-weight:600;">${titles[i]}</span><div id="decomp-${key}" style="height:140px;width:100%"></div></div>`
    ).join('');
    keys.forEach((key,i) => {
      const d = dc[key]||[];
      Plotly.newPlot(`decomp-${key}`, [{
x: d.map(r=>r.date), y: d.map(r=>r.value),
type:'scatter', mode:'lines', line:{color:cols[i],width:1.8},
      }], { margin:{t:0,b:25,l:60,r:15}, yaxis:{automargin:true}, xaxis:{tickformat:'%Y-%m',nticks:10} }, { responsive:true });
    });
  } catch(e) { document.getElementById('fc-decomp').innerHTML = `<div class="spinner" style="color:#E0556A;">分解加载失败: ${e}</div>`; }
}

// ═══════════════ 📋 明细 ═══════════════
async function loadDetail() {
  const el = document.getElementById('asec-detail');
  el.innerHTML = `
    <div class="chart-row">
      <div class="chart-box">
<h3>异常大额消费 (均值+3σ)</h3>
<div class="hint">红色虚线 = 阈值（均值 + 3 倍标准差）。超出此线的交易为统计异常，通常对应突发大额支出（如数码产品、医疗、旅行）。</div>
<div id="dt-anom" class="plot-md"><div class="spinner">加载中...</div></div>
      </div>
      <div class="chart-box">
<h3>节假日消费对比</h3>
<div class="hint">对比含节假日的周 vs 普通周的消费差异。春节、国庆等长假周通常表现为出行或购物支出增加。</div>
<div id="dt-holiday" class="plot-md"><div class="spinner">加载中...</div></div>
      </div>
    </div>
    <div class="chart-row full">
      <div class="chart-box">
<h3>商户消费 Top 12</h3>
<div class="hint">按总消费金额排名。结合 RFM（最近消费/消费频次/消费金额）可识别"高价值"或"即将流失"的商户。</div>
<div id="dt-merch" class="plot-lg"><div class="spinner">加载中...</div></div>
</div>
      </div>
    </div>
    <div class="chart-row">
      <div class="chart-box">
<h3>商户 RFM 气泡分布</h3>
<div class="hint">横轴 = 消费频次，纵轴 = 消费总金额。气泡越大 = 距今天数越大（越久未消费）。虚线 = 均值参考线。右上角 = 高频高金额的"高价值商户"。</div>
<div id="dt-rfm" class="plot-lg"><div class="spinner">加载中...</div></div>
      </div>
      <div class="chart-box">
      </div>
    </div>
    <div class="chart-row full">
      <div class="chart-box">
<h3>消费关联规则挖掘 (Apriori · 按周购物篮)</h3>
<div class="hint">
  以<b>商户级别</b>按周挖掘："买A的周也买B"的共现模式。仅保留出现≥5周、Lift>2.5、单商户对单商户的强关联。<br>
  <b>Lift > 2.5</b> = 前件出现时后件概率提升2.5倍以上。<b>置信度≥50%</b> = 半成把握前件出现则后件出现。<br>
  切换为<b>消费分类级别</b>可在品类粒度发现"外卖常与网购共存"等宏观模式。
</div>
<div class="controls">
  <select id="rules-level" onchange="loadRules()" style="font-size:12px;">
    <option value="merchant">商户级别 (推荐)</option>
	    <option value="goods">商品级别 🆕</option>
    <option value="category">消费分类级别</option>
  </select>
  <button onclick="loadRules()" style="font-size:13px;padding:8px 18px;">🧠 挖掘关联规则</button>
</div>
<div id="dt-rules">
  <div style="text-align:center;padding:20px;color:var(--muted2);">点击按钮开始挖掘</div>
</div>
      </div>
    </div>
  `;
  Promise.all([
    fetchJSON(`${API}/anomalies`).then(an => {
      const items = (an.items||[]).slice(0,12).reverse();
      Plotly.newPlot('dt-anom', [{
y: items.map(r => `${(r.order_time||'').slice(5,10)} | ${(r.keeper||'').slice(0,12)}`),
x: items.map(r=>r.order_amount), type:'bar', orientation:'h',
marker:{color:'#F97316',line:{width:0}},
text: items.map(r=>`¥${r.order_amount}`), textposition:'outside', textfont:{size:9},
      }], {
margin:{t:10,b:25,l:180,r:70}, xaxis:{automargin:true}, yaxis:{automargin:true},
shapes: [{type:'line',x0:an.threshold,x1:an.threshold,y0:-0.5,y1:items.length-0.5,line:{color:'#E0556A',dash:'dash',width:2}}],
annotations: [{x:an.threshold,y:items.length-1,text:`阈值 ¥${an.threshold?.toFixed(0)}`,showarrow:false,font:{color:'#E0556A',size:10},xanchor:'left'}],
      }, { responsive:true });
    }),
    fetchJSON(`${API}/holidays`).then(ho => {
      const ts=ho.total_stats||{}, a=ts['节假日周'], b=ts['非节假日周'];
      Plotly.newPlot('dt-holiday', [
{ x:['节假日周','非节假日周'], y:[a?.平均周总支出||0, b?.平均周总支出||0], type:'bar', name:'周均支出', marker:{color:'#4F6BED',line:{width:0}} },
{ x:['节假日周','非节假日周'], y:[a?.平均日均支出||0, b?.平均日均支出||0], type:'bar', name:'日均支出', marker:{color:'#E0556A',line:{width:0}} },
      ], { barmode:'group', ...LAYOUT(''), legend:{orientation:'h',y:1.08} }, { responsive:true });
    }),
    fetchJSON(`${API}/merchants`).then(m => {
      const t12 = (m.top10_amount||[]).slice(0,12).reverse();
      Plotly.newPlot('dt-merch', [{
y: t12.map(r=>r.keeper), x: t12.map(r=>r.monetary), type:'bar', orientation:'h',
marker:{color:'#4F6BED',line:{width:0}},
text: t12.map(r=>`¥${r.monetary?.toFixed(0)}`), textposition:'outside', textfont:{size:9},
      }], { margin:{t:10,b:25,l:280,r:70}, xaxis:{automargin:true}, yaxis:{automargin:true} }, { responsive:true });

      // RFM bubble
      const rfmData = m.rfm || [];
      if (rfmData.length) {
const freqVals = rfmData.map(r=>r.frequency), monVals = rfmData.map(r=>r.monetary);
const meanF = freqVals.reduce((a,b)=>a+b,0)/freqVals.length;
const meanM = monVals.reduce((a,b)=>a+b,0)/monVals.length;
Plotly.newPlot('dt-rfm', [{
  x: freqVals, y: monVals, type:'scatter', mode:'markers',
  marker:{ size: rfmData.map(r=>Math.max(8,r.recency*0.3+8)),
           color: rfmData.map(r=>r.recency), colorscale:[[0,'#4F6BED'],[0.5,'#8B5CF6'],[1,'#F97316']],
           showscale:true, colorbar:{title:'距今天数',len:0.5} },
  text: rfmData.map(r=>`<b>${r.keeper}</b><br>频次: ${r.frequency}<br>金额: ¥${r.monetary?.toFixed(0)}<br>最近: ${r.recency}天前`),
  hoverinfo:'text',
}], {
  margin:{t:20,b:40,l:70,r:20},
  xaxis:{title:'消费频次',automargin:true},
  yaxis:{title:'消费总金额 (元)',automargin:true},
  shapes: [{type:'line',x0:meanF,x1:meanF,y0:0,y1:Math.max(...monVals),line:{color:'#a0a5b8',dash:'dash',width:1}},
           {type:'line',x0:0,x1:Math.max(...freqVals),y0:meanM,y1:meanM,line:{color:'#a0a5b8',dash:'dash',width:1}}],
}, { responsive:true });
      }
    }),
  ]).catch(e=>console.error(e));
}

async function loadRules() {
  const el = document.getElementById('dt-rules');
  const level = document.getElementById('rules-level')?.value || 'merchant';
  el.innerHTML = '<div class="spinner">挖掘关联规则中...</div>';
  try {
    const ar = await fetchJSON(`${API}/association-rules?level=${level}`);
    const top = (ar.top20||[]).slice(0,15);
    const ruleCount = ar.count || 0;
    const levelLabel = level === 'merchant' ? '商户级别' : level === 'goods' ? '商品级别' : '消费分类级别';

    if (!top.length) {
      el.innerHTML = `<div style="text-align:center;padding:30px;color:var(--muted2);">
        📭 ${levelLabel} · 未发现满足条件的关联规则<br>
        <small>可尝试切换级别或降低参数阈值</small></div>`;
      return;
    }

    // Build node-link data for network view
    const nodes = new Map(), links = [];
    top.forEach((r, i) => {
      const a = r.antecedents, c = r.consequents;
      if (!nodes.has(a)) nodes.set(a, {label:a, count:0, lifts:[]});
      if (!nodes.has(c)) nodes.set(c, {label:c, count:0, lifts:[]});
      nodes.get(a).count++;
      nodes.get(c).count++;
      nodes.get(a).lifts.push(r.lift);
      nodes.get(c).lifts.push(r.lift);
      links.push({source:a, target:c, lift:r.lift, confidence:r.confidence, support:r.support});
    });
    const nodeArr = Array.from(nodes.values()).map(n => ({
      label: n.label, count: n.count,
      avgLift: n.lifts.reduce((a,b)=>a+b,0)/n.lifts.length
    }));

    el.innerHTML = `<div style="font-size:12px;color:var(--muted2);margin-bottom:6px;">
      ${levelLabel} · 共 ${ruleCount} 条强关联规则 · 按周购物篮</div>
      <div class="chart-grid" style="grid-template-columns:1fr 1fr;">
        <div class="chart-panel">
          <h4>🔗 关联网络图</h4>
          <div id="dt-rules-net" class="plot-lg"></div>
          <div class="net-legend">
            <span style="margin-right:12px;">节点颜色:</span>
            <span class="legend-dot" style="background:#4F6BED;"></span>低Lift
            <span class="legend-dot" style="background:#8B5CF6;"></span>中
            <span class="legend-dot" style="background:#F97316;"></span>高Lift
            <span style="margin-left:12px;">节点大小 = 关联规则数</span>
          </div>
        </div>
        <div class="chart-panel"><h4>📊 提升度排名 (Top 15)</h4><div id="dt-rules-bar" class="plot-lg"></div></div>
      </div>`;

    // Network graph
    const xNodes = [], yNodes = [], nodeText = [], nodeSize = [], nodeColor = [];
    const n = nodeArr.length;
    // Circular layout
    nodeArr.forEach((nd, i) => {
      const angle = (2 * Math.PI * i) / n - Math.PI/2;
      const r = 3 + n * 0.3;
      xNodes.push(r * Math.cos(angle));
      yNodes.push(r * Math.sin(angle));
      nodeText.push(nd.label.slice(0, 20));
      nodeSize.push(Math.max(12, nd.count * 8 + 8));
      nodeColor.push(nd.avgLift);
    });

    const edgeX = [], edgeY = [], edgeW = [];
    links.forEach(l => {
      const si = nodeArr.findIndex(nd => nd.label === l.source);
      const ti = nodeArr.findIndex(nd => nd.label === l.target);
      if (si >= 0 && ti >= 0) {
        edgeX.push(xNodes[si], xNodes[ti], null);
        edgeY.push(yNodes[si], yNodes[ti], null);
        edgeW.push(Math.max(1, l.lift * 1.5));
      }
    });

    Plotly.newPlot('dt-rules-net', [
      // edges
      { x: edgeX, y: edgeY, mode: 'lines', type: 'scatter',
        line: { color: '#c4b5fd', width: 1 }, hoverinfo: 'none', showlegend: false },
      // nodes
      { x: xNodes, y: yNodes, mode: 'markers+text', type: 'scatter',
        text: nodeText, textposition: 'top center', textfont: { size: 10, color: '#333' },
        marker: { size: nodeSize, color: nodeColor, colorscale: [[0,'#4F6BED'],[0.5,'#8B5CF6'],[1,'#F97316']],
                  showscale: true, colorbar: { title: '平均Lift', len: 0.5, x: 1.02 } },
        hovertext: nodeArr.map(nd => `<b>${nd.label}</b><br>关联规则数: ${nd.count}<br>平均Lift: ${nd.avgLift.toFixed(2)}`),
        hoverinfo: 'text', showlegend: false }
    ], { margin: { t: 10, b: 10, l: 10, r: 10 },
         xaxis: { showgrid: false, zeroline: false, showticklabels: false },
         yaxis: { showgrid: false, zeroline: false, showticklabels: false },
         plot_bgcolor: 'transparent', paper_bgcolor: 'transparent' }, { responsive: true });

    // Bar chart
    const displayTop = top.slice(0,15).reverse();
    const leftMargin = Math.max(200, Math.min(300, level === 'category' ? 320 : 240));
    Plotly.newPlot('dt-rules-bar', [{
      y: displayTop.map(r => `${r.antecedents} → ${r.consequents}`.slice(0, 55)),
      x: displayTop.map(r => r.lift), type: 'bar', orientation: 'h',
      marker: { color: displayTop.map(r => {
        const l = r.lift; return l >= 3 ? '#F97316' : l >= 2 ? '#8B5CF6' : '#4F6BED';
      }), line: { width: 0 }},
      text: displayTop.map(r => `Lift=${r.lift?.toFixed(2)} | 置信=${(r.confidence*100)?.toFixed(0)}% | 支持=${(r.support*100)?.toFixed(1)}%`),
      textposition: 'outside', textfont: { size: 9 },
    }], { margin: { t: 10, b: 25, l: leftMargin, r: 230 },
         xaxis: { title: '提升度 (Lift)', automargin: true },
         yaxis: { automargin: true } }, { responsive: true });

  } catch(e) { el.innerHTML = `<div class="spinner" style="color:#E0556A;">${e}</div>`; }
}

async function loadExpenseAnimation() {
  const el = document.getElementById('fc-anim');
  el.innerHTML = '<div class="spinner">构建动画中...</div>';
  try {
    const expData = await fetchJSON(`${API}/monthly-expense`);
    const months = expData.months||[], vals = expData.values||[];
    const budget = getBudget();
    const N = months.length;

    el.innerHTML = '<div id="fc-anim-plot" style="width:100%;height:550px;"></div>';
    await new Promise(r => requestAnimationFrame(r));
    await new Promise(r => setTimeout(r, 100));

    // Build frames with cumulative data + xaxis range per frame
    const frames = months.map((_, k) => ({
      name: `f${k}`,
      data: [{
x: months.slice(0, k + 1),
y: vals.slice(0, k + 1),
'marker.color': vals.slice(0, k + 1).map(v => v > budget ? '#E0556A' : '#2DA87A'),
'text': vals.slice(0, k + 1).map(v => `¥${v?.toFixed(0)}`),
      }],
      layout: { 'xaxis.range': [-0.5, k + 0.5] },
    }));

    // Show first 2 months initially so the line is visible
    const initN = Math.min(2, N);
    Plotly.newPlot('fc-anim-plot', [{
      x: months.slice(0, initN), y: vals.slice(0, initN),
      type: 'scatter', mode: 'lines+markers',
      marker: { size: 8,
        color: vals.slice(0, initN).map(v => v > budget ? '#E0556A' : '#2DA87A'),
        line: { width: 1, color: '#fff' } },
      line: { color: '#4F6BED', width: 3 },
      text: vals.slice(0, initN).map(v => `¥${v?.toFixed(0)}`), textposition: 'top center',
      textfont: { size: 10, color: '#333' },
      name: '月度支出', showlegend: false,
      hovertemplate: '%{x}<br>支出: ¥%{y:.2f}<extra></extra>',
    }], {
      title: { text: '📅 月度支出动态监控', x: 0.5, font: { size: 18, color: '#2C3E50' } },
      xaxis: { title: '月份', gridcolor: '#f0f0f0', zeroline: false, type: 'category',
       range: [-0.5, initN - 0.5], automargin: true },
      yaxis: { title: '支出金额 (元)', gridcolor: '#f0f0f0', zeroline: false,
       automargin: true, autorange: true },
      plot_bgcolor: '#fff', paper_bgcolor: '#F8F9FA',
      font: { color: '#555' },
      margin: { t: 70, b: 130, l: 70, r: 40 },
      shapes: [{
type: 'line', x0: months[0], x1: months[N-1], y0: budget, y1: budget,
line: { color: '#E0556A', dash: 'dash', width: 2 },
      }],
      annotations: [{
x: months[N-1], y: budget, xanchor: 'right', yanchor: 'bottom',
text: `月预算 ¥${budget}`, showarrow: false,
font: { color: '#E0556A', size: 13 }, bgcolor: 'rgba(255,255,255,0.8)',
borderpad: 4,
      }],
      updatemenus: [{
type: 'buttons', direction: 'left', x: 0.05, y: 1.08, xanchor: 'left',
pad: { r: 10, t: 10 },
buttons: [
  { label: '▶ 播放', method: 'animate',
    args: [null, { frame: { duration: 600, redraw: true }, fromcurrent: true,
                   transition: { duration: 400, easing: 'cubic-in-out' }, mode: 'immediate' }] },
  { label: '⏸ 暂停', method: 'animate',
    args: [[null], { frame: { duration: 0 }, mode: 'immediate' }] },
  { label: '⟳ 复位', method: 'animate',
    args: [['f0'], { frame: { duration: 300, redraw: true }, mode: 'immediate',
                      transition: { duration: 300 } }] },
],
      }],
      sliders: [{
active: 0, x: 0.05, y: -0.14, len: 0.9,
bgcolor: 'rgba(240,240,240,0.8)', bordercolor: '#CCC', borderwidth: 1,
currentvalue: { prefix: '当前月份: ', font: { size: 12, color: '#555' } },
steps: months.map((m, k) => ({
  label: m, method: 'animate',
  args: [[`f${k}`], { frame: { duration: 300, redraw: true }, mode: 'immediate',
                       transition: { duration: 300, easing: 'cubic-in-out' } }],
})),
      }],
    }, { responsive: true });
    // Attach frames
    Plotly.addFrames('fc-anim-plot', frames);

  } catch(e) { el.innerHTML = `<div class="spinner" style="color:#E0556A;">${e}</div>`; }
}

// ═══════════════ 💸 关系 ═══════════════
async function loadSocial() {
  const el = document.getElementById('asec-social');
  el.innerHTML = `
    <div class="chart-row">
      <div class="chart-box">
<h3>社交资金流向 Top 10</h3>
<div class="hint">绿 = 净流入（对方给我的钱多于我给对方的），红 = 净流出。只统计转账和红包交易。</div>
<div id="so-bar" class="plot-md"><div class="spinner">加载中...</div></div>
      </div>
      <div class="chart-box">
<h3>概览</h3>
<div id="so-summary"></div>
      </div>
    </div>
    <div class="chart-row full">
      <div class="chart-box">
<h3>💰 社交资金三维流向图</h3>
<div class="hint">
  🔵 中心蓝色菱形 = "我"。<br>
  🔴 红色线条和节点 = 净流入（对方给我钱），🟢 绿色 = 净流出（我给对方钱）。<br>
  <b>节点大小</b> = 交易频次（越大表示与这个人转账越频繁）。<br>
  <b>距中心距离</b> = 金额大小（越远表示涉及金额越大，对数映射）。<br>
  <b>Z 轴 (高度)</b> = 对数盈余（平面以上=净流入，平面以下=净流出）。<br>
  鼠标拖拽可旋转视图，滚轮缩放。
</div>
<div id="so-3d" class="plot-xl" style="height:650px;"><div class="spinner">加载中...</div></div>
      </div>
    </div>
  `;
  try {
    const sf = await fetchJSON(`${API}/social`);
    const all = [...(sf||[])].sort((a,b)=>Math.abs(b.盈余)-Math.abs(a.盈余));
    const sf10 = all.slice(0,10).reverse();
    Plotly.newPlot('so-bar', [{
      y: sf10.map(r=>r.keeper), x: sf10.map(r=>r.盈余), type:'bar', orientation:'h',
      marker:{color: sf10.map(r=>r.盈余>=0?'#2DA87A':'#E0556A'),line:{width:0}},
      text: sf10.map(r=>`${r.盈余>=0?'+':''}¥${Math.abs(r.盈余||0).toFixed(0)}`), textposition:'outside', textfont:{size:9},
    }], { margin:{t:10,b:25,l:160,r:80}, xaxis:{automargin:true}, yaxis:{automargin:true} }, { responsive:true });

    const inflow = all.filter(r=>r.盈余>0).reduce((s,r)=>s+r.盈余,0);
    const outflow = all.filter(r=>r.盈余<0).reduce((s,r)=>s+Math.abs(r.盈余),0);
    document.getElementById('so-summary').innerHTML = `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:6px;">
<div class="card" style="background:var(--success-bg);"><div class="value" style="font-size:22px;color:var(--success);">¥${inflow.toLocaleString()}</div><div class="label">总流入</div></div>
<div class="card" style="background:var(--danger-bg);"><div class="value" style="font-size:22px;color:var(--danger);">¥${outflow.toLocaleString()}</div><div class="label">总流出</div></div>
<div class="card" style="grid-column:span 2;">
  <div class="value" style="font-size:18px;color:${inflow>=outflow?'var(--success)':'var(--danger)'};">${inflow>=outflow?'净流入':'净流出'} ¥${Math.abs(inflow-outflow).toLocaleString()}</div>
  <div class="label">涉及 ${all.length} 人</div>
</div>
      </div>
    `;

    // 3D
    const allData = all.slice(0,25), n = allData.length;
    const angles = Array.from({length:n},(_,i)=>2*Math.PI*i/n);
    const surpluses = allData.map(r=>r.盈余||0);
    const freqs = allData.map(r=>r.总频次||1);
    const maxFreq = Math.max(...freqs,1), minFreq = Math.min(...freqs,1);
    const maxAbs = Math.max(...surpluses.map(Math.abs),1);
    const traces = [];
    const xs=[], ys=[], zs=[], sizes=[], ncolors=[];
    for (let i=0;i<n;i++) {
      const r = 2 + 3.5 * Math.log1p(Math.abs(surpluses[i])) / Math.log1p(maxAbs);
      const x = r*Math.cos(angles[i]), y = r*Math.sin(angles[i]);
      const z = Math.sign(surpluses[i]) * Math.log1p(Math.abs(surpluses[i]));
      const lw = 1.2 + 3 * (freqs[i]-minFreq)/(maxFreq-minFreq||1);
      traces.push({type:'scatter3d',mode:'lines',x:[0,x,null],y:[0,y,null],z:[0,z,null],
line:{color:surpluses[i]>=0?'#E0556A':'#4F6BED',width:lw},
hoverinfo:'text',text:`<b>${allData[i].keeper}</b><br>净盈余: ¥${surpluses[i].toFixed(2)}<br>频次: ${freqs[i]}次`,showlegend:false});
      xs.push(x); ys.push(y); zs.push(z);
      sizes.push(4+10*(freqs[i]-minFreq)/(maxFreq-minFreq||1));
      ncolors.push(surpluses[i]>=0?'#E0556A':'#4F6BED');
    }
    traces.push({type:'scatter3d',mode:'markers',x:xs,y:ys,z:zs,
      marker:{size:sizes,color:ncolors,line:{width:.5,color:'rgba(0,0,0,0.2)'}},
      hoverinfo:'text',text:allData.map((r,i)=>`<b>${r.keeper}</b><br>净盈余: ¥${surpluses[i].toFixed(2)}<br>频次: ${freqs[i]}次`),showlegend:false});
    traces.push({type:'scatter3d',mode:'markers+text',x:[0],y:[0],z:[0],
      marker:{size:12,color:'#4F6BED',symbol:'diamond',line:{width:2,color:'rgba(255,255,255,0.9)'}},
      text:['我'],textposition:'top center',textfont:{size:15,color:'#4F6BED'},hoverinfo:'none',showlegend:false});
    const maxR = Math.max(...xs.map(Math.abs),...ys.map(Math.abs))*1.25;
    const maxZ = Math.max(...zs.map(Math.abs))*1.35;
    Plotly.newPlot('so-3d', traces, {
      margin:{t:20,b:20,l:20,r:20},showlegend:false,
      scene:{xaxis:{showgrid:false,zeroline:false,showticklabels:false,title:'',range:[-maxR,maxR]},
     yaxis:{showgrid:false,zeroline:false,showticklabels:false,title:'',range:[-maxR,maxR]},
     zaxis:{showgrid:false,zeroline:false,showticklabels:false,title:'',range:[-maxZ,maxZ]},
     aspectmode:'cube',camera:{eye:{x:2.8,y:2.8,z:2.0}}},
      hovermode:'closest',
    }, { responsive:true });
  } catch(e) { el.innerHTML = `<div class="spinner" style="color:#E0556A;">${e}</div>`; }
}

// ═══════════════ 数据上传区 ═══════════════
let uploadedFiles = [];

// Drag & drop
(function(){
  const zone = document.getElementById('upload-zone');
  if (!zone) return;
  ['dragenter','dragover','dragleave','drop'].forEach(evt => {
    zone.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); });
  });
  ['dragenter','dragover'].forEach(evt => {
    zone.addEventListener(evt, () => zone.classList.add('drag-over'));
  });
  ['dragleave','drop'].forEach(evt => {
    zone.addEventListener(evt, () => zone.classList.remove('drag-over'));
  });
  zone.addEventListener('drop', e => {
    if (e.dataTransfer.files.length) handleFiles(e.dataTransfer.files);
  });
})();

async function handleFiles(fileList) {
  const status = document.getElementById('upload-status');
  for (const file of fileList) {
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['csv','xlsx','xls'].includes(ext)) {
      status.innerHTML = `<span style="color:#E0556A;">⚠️ 不支持 ${file.name}，仅接受 CSV / XLSX</span>`;
      return;
    }
  }
  for (const file of fileList) {
    status.textContent = `上传中: ${file.name} ...`;
    try {
      const form = new FormData(); form.append('file', file);
      const r = await fetch('/api/upload', { method:'POST', body:form });
      if (!r.ok) {
        const err = await r.json();
        status.innerHTML = `<span style="color:#E0556A;">⚠️ ${err.error || err.message}</span>`;
        return;
      }
      const data = await r.json();
      uploadedFiles.push(data.filename);
    } catch(e) {
      status.innerHTML = `<span style="color:#E0556A;">⚠️ 上传失败: ${e}</span>`;
      return;
    }
  }
  status.textContent = `✅ 已添加 ${fileList.length} 个文件`;
      showToast('📂 已添加 ' + fileList.length + ' 个文件到待合并列表', 'info');
  renderFileTags();
}

function renderFileTags() {
  const el = document.getElementById('file-list');
  el.innerHTML = uploadedFiles.map(f => `
    <span class="file-tag">
      ${f}
      <button class="del-btn" data-filename="${f.replace(/"/g, '&quot;')}" onclick="removeFile(this.getAttribute('data-filename'))">×</button>
    </span>
  `).join('');
  document.getElementById('merge-btn').style.display = uploadedFiles.length ? '' : 'none';
  document.getElementById('merge-result').className = 'merge-result';
}

async function removeFile(filename) {
  try {
    await fetch(`/api/uploads/${encodeURIComponent(filename)}`, { method:'DELETE' });
  } catch(e) {}
  uploadedFiles = uploadedFiles.filter(f => f !== filename);
  renderFileTags();
}

async function triggerMerge() {
  const btn = document.getElementById('merge-btn');
  const resultEl = document.getElementById('merge-result');
  btn.disabled = true; btn.textContent = '⏳ 合并中...';
  resultEl.className = 'merge-result';

  try {
    const r = await fetch('/api/merge-and-clean', { method:'POST' });
    const data = await r.json();
    if (r.ok) {
      showToast('✅ 合并成功！原有 ' + data.old_count + ' 条 → ' + data.new_count + ' 条 (+' + data.added + ')，耗时 ' + data.elapsed_seconds + 's', 'success');
      // Clear predata files from UI
      uploadedFiles = [];
      renderFileTags();
      // Refresh the dashboard
      document.getElementById('summary-cards').innerHTML = '<div class="spinner">数据已更新，刷新中...</div>';
      Object.keys(loaded).forEach(k => delete loaded[k]);
      init();
    } else {
      showToast('❌ 合并失败: ' + data.message + ' · ' + (data.rollback || ''), 'error');
    }
  } catch(e) {
    showToast('❌ 网络错误: ' + e, 'error');
  }
  btn.disabled = false; btn.textContent = '⚡ 合并到主数据';
}

async function triggerClearData() {
  const btn = document.getElementById('clear-data-btn');
  if (!confirm('⚠️ 确定要清除所有账单数据、日志和缓存吗？\n\n此操作不可逆！')) return;

  btn.disabled = true; btn.textContent = '⏳ 清除中...';
  try {
    const r = await fetch('/api/clear-data', { method: 'POST' });
    const data = await r.json();
    if (r.ok) {
      showToast('✅ 已清除 ' + data.removed.length + ' 项数据', 'success');
      // 清空前端状态
      uploadedFiles = [];
      renderFileTags();
      document.getElementById('merge-btn').style.display = 'none';
      document.getElementById('summary-cards').innerHTML = '<div class="spinner">数据已清除，刷新中...</div>';
      Object.keys(loaded).forEach(k => delete loaded[k]);
      init();
    } else {
      showToast('❌ 清除失败: ' + data.message, 'error');
    }
  } catch (e) {
    showToast('❌ 网络错误: ' + e, 'error');
  }
  btn.disabled = false; btn.textContent = '🗑 清除所有数据';
}

// ═══════════════ 图表全屏放大 ═══════════════
function injectExpandButtons(container) {
  if (!container) return;
  container.querySelectorAll('.chart-panel').forEach(function(box) {
    if (box.querySelector('.chart-expand')) return;
    var btn = document.createElement('button');
    btn.className = 'chart-expand'; btn.innerHTML = '⛶'; btn.title = '全屏查看';
    btn.onclick = function(e) { e.stopPropagation(); openFullscreen(box); };
    box.appendChild(btn);
  });
}

function openFullscreen(box) {
  var body = document.getElementById('fs-body');
  body.innerHTML = '';
  var clone = box.cloneNode(true);
  var del = clone.querySelector('.chart-expand'); if (del) del.remove();
  var hint = clone.querySelector('.hint'); if (hint) hint.style.display = 'none';
  clone.style.cssText = 'width:100%;height:100%;';
  body.appendChild(clone);
  document.getElementById('chart-fullscreen').classList.add('show');
  setTimeout(function() {
    body.querySelectorAll('.js-plotly-plot').forEach(function(p) { try { Plotly.Plots.resize(p); } catch(_){} });
  }, 200);
}

function closeFullscreen() {
  document.getElementById('chart-fullscreen').classList.remove('show');
}

(function() {
  var fs = document.getElementById('chart-fullscreen');
  if (fs) fs.addEventListener('click', function(e) { if (e.target === e.currentTarget) closeFullscreen(); });
  var sections = document.getElementById('sections');
  if (sections) new MutationObserver(function(mutations) {
    mutations.forEach(function(m) {
      m.addedNodes.forEach(function(node) { if (node.nodeType === 1) injectExpandButtons(node); });
    });
  }).observe(sections, { childList: true, subtree: true });
})();

init();