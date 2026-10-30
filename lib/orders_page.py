"""docs/orders.html — Dipin-ന്റെ "NSE Order Inflow Tracker" dashboard, ഡാറ്റ GitHub-ൽ നിന്ന് സ്വയം (CSV import വേണ്ട)."""
import json
from pathlib import Path

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>NSE Order Inflow Tracker</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;700&family=Noto+Sans+Malayalam:wght@400;600&display=swap" rel="stylesheet">
<style>
:root{--bg:#eef2f6;--panel:#fff;--ink:#14213d;--mute:#5f6b7e;--line:#d8dfe8;--gain:#0b7a6b;--loss:#c8453b;--accent:#2f4bd8;--accent2:#1f5f8b;--soft:#e3e9fb;--gainbg:#e1f3ef;--lossbg:#fbe9e7;--fire:#c2410c}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f1624;--panel:#18223a;--ink:#e8edf7;--mute:#98a4ba;--line:#2a3652;--gain:#3ec7b0;--loss:#ff7d72;--accent:#7f95ff;--accent2:#6fb3e0;--soft:#27304f;--gainbg:#143b3a;--lossbg:#40222a;--fire:#fb923c}}
:root[data-theme="dark"]{--bg:#0f1624;--panel:#18223a;--ink:#e8edf7;--mute:#98a4ba;--line:#2a3652;--gain:#3ec7b0;--loss:#ff7d72;--accent:#7f95ff;--accent2:#6fb3e0;--soft:#27304f;--gainbg:#143b3a;--lossbg:#40222a;--fire:#fb923c}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 Figtree,"Noto Sans Malayalam",system-ui,sans-serif;font-variant-numeric:tabular-nums}
main{max-width:1100px;margin:0 auto;padding:20px 16px 48px}
a{color:var(--accent)}
header{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;margin-bottom:6px}
h1{font-size:22px;margin:0}h2{font-size:15px;margin:0 0 12px}
.note{color:var(--mute);font-size:13px;margin:0 0 16px;max-width:80ch}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:16px;margin-bottom:14px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.kpi{border-left:3px solid var(--accent);padding-left:10px}
.kpi span{color:var(--mute);font-size:13px}.kpi b{display:block;font-size:22px}
.grid2{display:grid;grid-template-columns:minmax(0,1fr);gap:14px}
@media(min-width:800px){.grid2{grid-template-columns:minmax(0,1.3fr) minmax(0,1fr)}}
label{display:flex;flex-direction:column;font-size:12px;color:var(--mute);gap:3px}
input,select,button{font:inherit;color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:7px 9px;min-width:0}
button{cursor:pointer;background:var(--panel)}
:focus-visible{outline:2px solid var(--accent2);outline-offset:2px}
.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}
th.n,td.n{text-align:right}
th{color:var(--mute);font-weight:500;font-size:12px}
th.s{cursor:pointer}th.s:hover{color:var(--ink)}
.tag{padding:1px 8px;border-radius:99px;font-size:12px;background:var(--soft);color:var(--accent)}
.up{color:var(--gain)}.down{color:var(--loss)}.muted{color:var(--mute)}.fire{color:var(--fire);font-weight:700}
.bars .r{display:grid;grid-template-columns:110px 1fr 90px;gap:8px;align-items:center;margin:7px 0;font-size:14px}
.bar{height:10px;border-radius:3px;background:var(--line);position:relative}
.bar i{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:var(--accent2)}
.alert{background:var(--soft);border:1px solid var(--accent);border-left-width:5px;border-radius:8px;padding:12px 16px;margin-bottom:14px}.alert ul{margin:6px 0 4px;padding-left:18px}
.empty{padding:26px;text-align:center;color:var(--mute)}
svg text{fill:var(--mute);font-size:11px}
td.t{max-width:340px;overflow:hidden;text-overflow:ellipsis}
.po{display:none}@media(max-width:640px){.ph{display:none}.po{display:inline}td.t{max-width:160px}th,td{padding:7px 6px}}
</style>
</head>
<body>
<main>
<p><a href="index.html">← എല്ലാ റിപ്പോർട്ടുകളും</a> · <a href="strategy.html">📋 Strategy</a></p>
<header>
  <h1>NSE order inflow tracker</h1>
  <div class="row"><button id="csv">Export CSV</button></div>
</header>
<p class="note">NSE-ൽ കമ്പനികൾ പ്രഖ്യാപിക്കുന്ന പുതിയ orders ദിവസവും സ്വയം ചേർക്കും (Market Agent, വൈകിട്ട് 5:17). Values ₹ crore-ൽ; filing PDF-ൽ നിന്ന് കണ്ടെത്തിയത് — തെറ്റാകാം, 📄 തുറന്ന് ഉറപ്പാക്കുക. <b>% വിൽപ്പന/വർഷം</b> = order ÷ കഴിഞ്ഞ 4 ക്വാർട്ടറിലെ വിൽപ്പന, പല വർഷത്തെ order ആണെങ്കിൽ വർഷങ്ങൾ കൊണ്ട് ഭാഗിച്ചത് (filing-ലെ execution കാലാവധി; കിട്ടിയില്ലെങ്കിൽ ഒരു വർഷം എന്ന് കണക്കാക്കും): 10%+ ശ്രദ്ധിക്കേണ്ടത്, 🔥 25%+ വലുത്. ⚠️ = വിൽപ്പനയുടെ 100%+ / mcap-ന്റെ 50%+ — തെറ്റായി വായിച്ചതാകാം, 📄 തുറന്ന് ഉറപ്പാക്കുക. ↺ = ഒരേ order വീണ്ടും (കണക്കിൽ കൂട്ടില്ല). JV = consortium / JV (കമ്പനിയുടെ പങ്ക് കുറവായിരിക്കാം). <span id="upd"></span></p>

<div id="alert"></div>

<section class="panel row" aria-label="Filters">
  <label>Period<select id="fper"><option value="all">All time</option><option value="fy">This financial year</option><option value="90">Last 90 days</option><option value="30">Last 30 days</option></select></label>
  <label>Industry<select id="fsec"><option value="">All industries</option></select></label>
  <label>Company<input id="fq" placeholder="Search company or symbol"></label>
  <label>കുറഞ്ഞ % വിൽപ്പന/വർഷം<input type="number" id="fmin" min="0" step="5" value="0"></label>
  <label style="flex-direction:row;align-items:center;gap:6px;padding-top:16px"><input type="checkbox" id="fcap" checked> mcap ₹500 cr+ മാത്രം</label>
  <label>Alert: % വിൽപ്പന<input type="number" id="athr" min="0" step="5" value="10"></label>
</section>

<section class="panel kpis" id="kpis"></section>

<section class="grid2">
  <div class="panel"><h2>Monthly order inflow (₹ crore)</h2><div id="monthly"></div></div>
  <div class="panel bars"><h2>Top companies by inflow</h2><div id="bycomp"></div></div>
</section>

<section class="grid2">
  <div class="panel bars"><h2>Inflow by industry</h2><div id="bysec"></div></div>
  <div class="panel"><h2>🔬 എന്താണ് ഫലിക്കുന്നത്</h2><p class="note" style="margin-bottom:8px">Order announcement-ന് മുമ്പുള്ള close-ൽ നിന്ന് 1 / 5 / 20 ട്രേഡിംഗ് ദിവസത്തെ ശരാശരി % (താഴെ: ജയം % · എണ്ണം). ആഴ്ചകൾ കഴിയുമ്പോൾ നിറയും.</p><div class="scroll" id="works"></div></div>
</section>

<section class="panel"><h2>Order log</h2>
  <div class="row" style="margin-bottom:10px">
    <label>ക്രമം<select id="osort">
      <option value="date">തീയതി (പുതിയത് ആദ്യം)</option><option value="sales">% വിൽപ്പന/വർഷം (കൂടിയത് ആദ്യം)</option><option value="exec">കാലാവധി</option>
      <option value="value">Order value</option><option value="mcap">% mcap</option>
      <option value="d1">D1 %</option><option value="d5">D5 %</option><option value="d20">D20 %</option><option value="symbol">പേര് (A–Z)</option>
    </select></label>
    <button type="button" id="tv-copy">📋 Copy to TradingView</button><button type="button" id="tv-file">⬇️ .txt</button>
  </div>
  <p class="note" id="tv-msg" style="margin:0 0 8px">TradingView-ലേക്ക്: മുകളിലെ filters (Period, Industry, കുറഞ്ഞ %, mcap ₹500 cr+) അനുസരിച്ചുള്ള ലിസ്റ്റ്, ഈ ക്രമത്തിൽ, ആവർത്തനം ഒഴിവാക്കി. ഉദാ: "കുറഞ്ഞ % വിൽപ്പന/വർഷം" 10 ആക്കിയാൽ വലിയ orders മാത്രം.</p>
  <div class="scroll" id="tbl"></div></section>
</main>
<script type="application/json" id="odata">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('odata').textContent);
const orders = D.orders || [];
const $ = id => document.getElementById(id);
const cr = n => n == null ? '–' : '₹' + Math.round(n).toLocaleString('en-IN') + ' cr';
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const pc = v => v == null ? '<span class="muted">–</span>' : `<span class="${v >= 0 ? 'up' : 'down'}">${v >= 0 ? '+' : ''}${v.toFixed(1)}%</span>`;
const dmy = s => { const [y, m, d] = s.split('-'); return `${d}/${m}/${y.slice(2)}`; };
const sales = o => o.pct_year == null ? '<span class="muted">–</span>' : `<span class="${o.pct_year >= 25 ? 'fire' : o.pct_year >= 10 ? 'up' : ''}" title="ആകെ: വിൽപ്പനയുടെ ${o.pct_sales}%${o.exec_m ? ' · ' + o.exec_m + ' മാസം കൊണ്ട്' : ' · കാലാവധി കിട്ടിയില്ല'}">${o.pct_year >= 25 ? '🔥 ' : ''}${o.pct_year.toFixed(1)}%</span>${o.chk ? ' <span title="വിൽപ്പനയുടെ 100%+ / mcap-ന്റെ 50%+ — filing തുറന്ന് ഉറപ്പാക്കുക">⚠️</span>' : ''}`;
const em = o => o.exec_m ? (o.exec_m >= 24 && o.exec_m % 12 === 0 ? o.exec_m / 12 + ' വർഷം' : o.exec_m + ' മാസം') : '–';
const ret = (o, h) => { const c = Object.keys(o.series || {}).sort().map(k => o.series[k]); return o.base && c.length >= h ? (c[h - 1] / o.base - 1) * 100 : null; };
let athr = 10, sortK = 'date', sortAsc = false, tvSyms = [];
const setSort = (k, asc) => { sortK = k; sortAsc = asc; try { localStorage.setItem('ord-sort', sortK); localStorage.setItem('ord-asc', sortAsc ? '1' : '0'); } catch (e) {} render(); };
try { athr = +(localStorage.getItem('ord-alert-pct') || 10); sortK = localStorage.getItem('ord-sort') || 'date'; sortAsc = localStorage.getItem('ord-asc') === '1'; } catch (e) {}
$('athr').value = athr;
$('upd').textContent = D.updated ? `അവസാനം പുതുക്കിയത്: ${dmy(D.updated)}.` : '';
[...new Set(orders.map(o => o.industry).filter(Boolean))].sort().forEach(s => $('fsec').add(new Option(s, s)));

function filtered() {
  const per = $('fper').value, sec = $('fsec').value, q = $('fq').value.trim().toLowerCase(), mn = +$('fmin').value || 0;
  const now = new Date(), fy = new Date(now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1, 3, 1).toISOString().slice(0, 10);
  const ago = d => new Date(Date.now() - d * 864e5).toISOString().slice(0, 10);
  return orders.filter(o => (per === 'all' || (per === 'fy' && o.date >= fy) || (+per && o.date >= ago(+per)))
    && (!sec || o.industry === sec) && (!q || (o.name + o.symbol).toLowerCase().includes(q)) && (!mn || (o.pct_year || 0) >= mn)
    && (!$('fcap').checked || (o.mcap || 0) >= 500));
}
const counted = l => l.filter(o => !o.dup && o.value);
function group(list, key) { const m = {}; counted(list).forEach(o => m[key(o)] = (m[key(o)] || 0) + o.value); return Object.entries(m).sort((a, b) => b[1] - a[1]); }
function bars(el, e, n) {
  const mx = Math.max(1, ...e.map(a => a[1]));
  $(el).innerHTML = e.length ? e.slice(0, n).map(([k, v]) => `<div class="r"><span title="${esc(k)}" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(k)}</span><div class="bar"><i style="width:${v / mx * 100}%"></i></div><span style="text-align:right">${cr(v)}</span></div>`).join('') : '<div class="empty">No orders match these filters.</div>';
}
function alerts() {
  const lim = new Date(Date.now() - 7 * 864e5).toISOString().slice(0, 10);
  const big = orders.filter(o => !o.dup && o.date >= lim && (o.pct_year || 0) >= athr && (o.mcap || 0) >= 500).sort((a, b) => b.pct_year - a.pct_year);
  $('alert').innerHTML = big.length ? `<div class="alert" role="alert"><b>കഴിഞ്ഞ 7 ദിവസത്തിൽ ${big.length} വലിയ order</b> (വിൽപ്പനയുടെ ${athr}%+, mcap ₹500 cr+)<ul>${big.slice(0, 8).map(o => `<li><b>${esc(o.symbol)}</b> ${cr(o.value)} · ${sales(o)} വർഷ വിൽപ്പന · ${dmy(o.date)}</li>`).join('')}</ul></div>` : '';
}
$('athr').addEventListener('input', () => { athr = +$('athr').value || 0; try { localStorage.setItem('ord-alert-pct', athr); } catch (e) {} alerts(); });

function render() {
  const l = filtered(), c = counted(l), tot = c.reduce((a, o) => a + o.value, 0);
  const big = c.slice().sort((a, b) => b.value - a.value)[0], topSec = group(l, o => o.industry || 'Other')[0];
  const sig = l.filter(o => !o.dup && (o.pct_year || 0) >= 10).length;
  const k = [['Total order inflow', c.length ? cr(tot) : '–'], ['Orders announced', l.filter(o => !o.dup).length], ['Companies', new Set(l.map(o => o.symbol)).size],
             ['വിൽപ്പനയുടെ 10%+', sig], ['Largest order', big ? `${cr(big.value)} (${esc(big.symbol)})` : '–'], ['Top industry', topSec ? esc(topSec[0]) : '–'],
             ['Value ഇല്ലാത്തവ', l.filter(o => !o.value).length]];
  $('kpis').innerHTML = k.map(([a, b]) => `<div class="kpi"><span>${a}</span><b>${b}</b></div>`).join('');
  const mo = group(l, o => o.date.slice(0, 7)).sort((a, b) => a[0].localeCompare(b[0])).slice(-12);
  if (!mo.length) $('monthly').innerHTML = '<div class="empty">ഡാറ്റ ഇല്ല.</div>';
  else {
    const W = 560, H = 210, L = 56, B = 24, T = 10, mx = Math.max(...mo.map(a => a[1])), bw = (W - L - 6) / mo.length;
    const mn = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const grid = [0, .5, 1].map(f => { const y = T + (1 - f) * (H - T - B); return `<line x1="${L}" x2="${W}" y1="${y}" y2="${y}" stroke="var(--line)"/><text x="${L - 6}" y="${y + 4}" text-anchor="end">${Math.round(mx * f).toLocaleString('en-IN')}</text>`; }).join('');
    const b = mo.map(([m, v], i) => { const h = v / mx * (H - T - B), x = L + i * bw + bw * .15; return `<rect x="${x}" y="${H - B - h}" width="${bw * .7}" height="${h}" rx="2" fill="var(--accent)"><title>${m}: ${cr(v)}</title></rect><text x="${x + bw * .35}" y="${H - 8}" text-anchor="middle">${mn[+m.slice(5) - 1]}</text>`; }).join('');
    $('monthly').innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Monthly order inflow">${grid}${b}</svg>`;
  }
  bars('bycomp', group(l, o => o.symbol), 8); bars('bysec', group(l, o => o.industry || 'Other'), 8);
  const keys = { date: o => o.date + (o.time || ''), symbol: o => o.symbol, value: o => o.value ?? -1, sales: o => o.pct_year ?? -1, exec: o => o.exec_m ?? -1, mcap: o => o.pct_mcap ?? -1,
                 d1: o => ret(o, 1) ?? -999, d5: o => ret(o, 5) ?? -999, d20: o => ret(o, 20) ?? -999 };
  if (!keys[sortK]) sortK = 'date';
  const rows = l.slice().sort((a, b) => { const x = keys[sortK](a), y = keys[sortK](b); const r = x < y ? 1 : x > y ? -1 : 0; return sortAsc ? -r : r; });
  $('osort').value = sortK;
  tvSyms = [...new Set(rows.filter(o => !o.dup).map(o => o.symbol))];
  const th = (k, t, cls = '') => `<th class="s ${cls}" data-k="${k}">${t}${sortK === k ? (sortAsc ? ' ▲' : ' ▼') : ''}</th>`;
  $('tbl').innerHTML = rows.length ? `<table><thead><tr>${th('date', 'Date', 'ph')}${th('symbol', 'Symbol')}<th class="ph">Industry</th><th class="ph">Order</th>${th('value', 'Value', 'n')}${th('sales', '% വിൽപ്പന<br>/വർഷം', 'n')}${th('exec', 'കാലാവധി', 'n ph')}${th('mcap', '% mcap', 'n ph')}${th('d1', 'D1', 'n')}${th('d5', 'D5', 'n ph')}${th('d20', 'D20', 'n ph')}<th></th></tr></thead><tbody>${rows.map(o => `<tr${o.dup ? ' class="muted"' : ''}><td class="ph">${dmy(o.date)}</td><td><b>${esc(o.symbol)}</b><small class="po muted"><br>${dmy(o.date)}</small>${o.dup ? ' ↺' : ''}${o.cons ? ' <span class="tag">JV</span>' : ''}</td><td class="ph"><span class="tag">${esc(o.industry || '–')}</span></td><td class="t ph" title="${esc(o.title)}">${esc(o.title)}</td><td class="n">${o.value ? (o.note === 'range' ? '≥' : '') + cr(o.value) : '<span class="muted">value ഇല്ല</span>'}</td><td class="n">${sales(o)}</td><td class="n ph">${em(o)}</td><td class="n ph">${o.pct_mcap == null ? '–' : o.pct_mcap.toFixed(1) + '%'}</td><td class="n">${pc(ret(o, 1))}</td><td class="n ph">${pc(ret(o, 5))}</td><td class="n ph">${pc(ret(o, 20))}</td><td>${o.file ? `<a href="${esc(o.file)}" target="_blank" rel="noopener" aria-label="Filing">📄</a>` : ''}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">No orders match these filters.</div>';
  $('tbl').querySelectorAll('th.s').forEach(t => t.addEventListener('click', () => {
    const k = t.dataset.k; setSort(k, sortK === k ? !sortAsc : k === 'symbol');
  }));
  const W = (D.works || []).filter(w => w.n);
  const cell = x => x && x.avg != null ? `<span class="${x.avg >= 0 ? 'up' : 'down'}">${x.avg >= 0 ? '+' : ''}${x.avg}%</span><br><small class="muted">${x.win}%·${x.n}</small>` : '<span class="muted">—</span>';
  $('works').innerHTML = W.length ? `<table><thead><tr><th>ഗ്രൂപ്പ്</th><th class="n">D1</th><th class="n">D5</th><th class="n">D20</th></tr></thead><tbody>${W.map(w => `<tr><td style="white-space:normal">${esc(w.g)} <small class="muted">(${w.n})</small></td><td class="n">${cell(w.d1)}</td><td class="n">${cell(w.d5)}</td><td class="n">${cell(w.d20)}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">ഡാറ്റ ഇല്ല.</div>';
  alerts();
}
['fper', 'fsec'].forEach(i => $(i).addEventListener('change', render)); ['fq', 'fmin'].forEach(i => $(i).addEventListener('input', render)); $('fcap').addEventListener('change', render);
$('csv').addEventListener('click', () => {
  const q = s => '"' + String(s == null ? '' : s).replace(/"/g, '""') + '"';
  const h = 'date,symbol,company,industry,value_cr,pct_sales,pct_sales_per_year,exec_months,pct_mcap,check,duplicate,title,filing\n' + orders.map(o => [o.date, o.symbol, q(o.name), q(o.industry), o.value ?? '', o.pct_sales ?? '', o.pct_year ?? '', o.exec_m ?? '', o.pct_mcap ?? '', o.chk ? 1 : 0, o.dup ? 1 : 0, q(o.title), o.file].join(',')).join('\n');
  const a = document.createElement('a'); a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(h); a.download = 'order-inflow.csv'; a.click();
});
$('osort').addEventListener('change', () => setSort($('osort').value, $('osort').value === 'symbol'));
const tvText = () => tvSyms.map(s => 'NSE:' + s.replace(/[&-]/g, '_')).join(',');
const tvMsg = t => $('tv-msg').textContent = t;
$('tv-copy').addEventListener('click', async () => {
  if (!tvSyms.length) return tvMsg('ലിസ്റ്റിൽ ഒന്നുമില്ല — filters മാറ്റുക');
  const t = tvText();
  try { await navigator.clipboard.writeText(t); }
  catch (e) { const ta = document.createElement('textarea'); ta.value = t; document.body.appendChild(ta); ta.select(); try { document.execCommand('copy'); } catch (e2) {} ta.remove(); }
  tvMsg(`✓ ${tvSyms.length} symbol കോപ്പി ചെയ്തു — TradingView watchlist-ൽ "Add symbol" ബോക്സിൽ paste ചെയ്യുക`);
});
$('tv-file').addEventListener('click', () => {
  if (!tvSyms.length) return tvMsg('ലിസ്റ്റിൽ ഒന്നുമില്ല — filters മാറ്റുക');
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([tvText()], { type: 'text/plain' }));
  a.download = 'orders-' + (D.updated || 'list') + '.txt'; document.body.appendChild(a); a.click(); a.remove();
  tvMsg('✓ ഫയൽ ഡൗൺലോഡ് ചെയ്തു — TradingView watchlist മെനു → Import list');
});
render();
</script>
</body>
</html>
"""


def build(out_dir, data):
    if not data:
        return
    slim = {"updated": data.get("updated"), "works": data.get("works"),
            "orders": [{k: v for k, v in o.items() if k not in ("added",)} for o in data.get("orders", [])]}
    js = json.dumps(slim, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    (Path(out_dir) / "orders.html").write_text(PAGE.replace("__DATA__", js), encoding="utf-8")
