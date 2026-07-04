"""Local web dashboard — serves a single-page HTML report."""
from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

_REPORT_JSON: str = "{}"
_HISTORY_JSON: str = "[]"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>repocheck dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0d1117; color: #e6edf3; min-height: 100vh; padding: 2rem; }
  h1 { font-size: 1.4rem; font-weight: 600; margin-bottom: 0.25rem; }
  .meta { color: #8b949e; font-size: 0.85rem; margin-bottom: 1.5rem; }
  .top-row { display: flex; align-items: center; gap: 1.5rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
  .score-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 1.5rem 2.5rem; text-align: center; }
  .score-number { font-size: 3.5rem; font-weight: 700; line-height: 1; }
  .score-grade { font-size: 1.2rem; color: #8b949e; margin-top: 0.25rem; }
  .refresh-badge { display: inline-flex; align-items: center; gap: 0.4rem; background: #161b22; border: 1px solid #30363d; border-radius: 20px; padding: 0.35rem 0.75rem; font-size: 0.8rem; color: #8b949e; }
  .refresh-dot { width: 7px; height: 7px; border-radius: 50%; background: #3fb950; animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
  .history-section { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1.25rem 1.5rem; margin-bottom: 1.5rem; }
  .section-title { font-size: 0.78rem; font-weight: 600; color: #8b949e; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 1rem; }
  .checks { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; }
  .check-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1rem 1.25rem; }
  .check-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
  .check-name { font-weight: 600; font-size: 0.9rem; }
  .check-score { font-size: 1.1rem; font-weight: 700; }
  .bar-bg { background: #21262d; border-radius: 4px; height: 6px; margin-bottom: 0.75rem; }
  .bar-fill { height: 6px; border-radius: 4px; transition: width 0.6s ease; }
  .details { font-size: 0.78rem; color: #8b949e; line-height: 1.6; }
  .detail-item { padding: 0.1rem 0; }
  .detail-item.bad { color: #f85149; }
  .detail-item.good { color: #3fb950; }
  .fix-section { margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid #21262d; }
  .fix-title { font-size: 0.7rem; font-weight: 600; color: #d29922; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
  .fix-item { display: flex; align-items: flex-start; gap: 0.5rem; font-size: 0.78rem; color: #e6edf3; padding: 0.2rem 0; cursor: pointer; }
  .fix-item input[type="checkbox"] { margin-top: 0.15rem; flex-shrink: 0; accent-color: #d29922; cursor: pointer; }
  .fix-item span { line-height: 1.4; }
  .fix-item:has(input:checked) span { text-decoration: line-through; color: #8b949e; }
  .A { color: #3fb950; } .B { color: #58a6ff; } .C { color: #d29922; } .D { color: #f0883e; } .F { color: #f85149; }
  .bar-A { background: #3fb950; } .bar-B { background: #58a6ff; } .bar-C { background: #d29922; } .bar-D { background: #f0883e; } .bar-F { background: #f85149; }
  footer { margin-top: 2rem; color: #8b949e; font-size: 0.8rem; }
  footer a { color: #58a6ff; text-decoration: none; }
</style>
</head>
<body>
<div id="app">Loading...</div>
<script>
const gradeColor = g => ({'A':'#3fb950','B':'#58a6ff','C':'#d29922','D':'#f0883e','F':'#f85149'}[g]||'#8b949e');
const isActionable = d => d.startsWith('No ') || d.toLowerCase().includes('consider') ||
    d.includes('appears inactive') || d.includes('low-effort') || d.startsWith('Short ');
const isGood = d => !isActionable(d);

const params = new URLSearchParams(window.location.search);
const watchSec = parseInt(params.get('watch') || '0');

let cachedHistory = null;
let histChart = null;

function renderHistoryChart() {
  const container = document.getElementById('history-container');
  if (!container || !cachedHistory || cachedHistory.length < 2) return;
  container.style.display = 'block';
  const canvas = document.getElementById('historyChart');
  if (!canvas) return;
  if (histChart) { histChart.destroy(); histChart = null; }

  const labels = cachedHistory.map(r => r.timestamp.substring(0, 16).replace('T', ' '));
  const scores = cachedHistory.map(r => r.score);
  const ptColors = scores.map(s => s>=90?'#3fb950':s>=80?'#58a6ff':s>=70?'#d29922':s>=60?'#f0883e':'#f85149');

  histChart = new Chart(canvas.getContext('2d'), {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Score',
        data: scores,
        borderColor: '#58a6ff',
        backgroundColor: 'rgba(88,166,255,0.08)',
        pointBackgroundColor: ptColors,
        pointBorderColor: ptColors,
        pointRadius: 5,
        pointHoverRadius: 7,
        tension: 0.35,
        fill: true,
      }]
    },
    options: {
      responsive: true,
      scales: {
        y: {
          min: 0, max: 100,
          grid: { color: '#21262d' },
          ticks: { color: '#8b949e', stepSize: 20 },
          border: { color: '#30363d' }
        },
        x: {
          grid: { color: '#21262d' },
          ticks: { color: '#8b949e', maxRotation: 30, maxTicksLimit: 8 },
          border: { color: '#30363d' }
        }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#161b22',
          borderColor: '#30363d',
          borderWidth: 1,
          titleColor: '#e6edf3',
          bodyColor: '#8b949e',
          callbacks: { label: ctx => ' Score: ' + ctx.parsed.y + '/100' }
        }
      }
    }
  });
}

function renderReport(data) {
  let refreshBadge = '';
  if (watchSec > 0) {
    refreshBadge = '<div class="refresh-badge"><span class="refresh-dot"></span><span id="refresh-label">Refreshing every ' + watchSec + 's</span></div>';
  }

  let html = '<h1>repocheck: ' + data.repo + '</h1>' +
    '<div class="meta">&#9733; ' + (data.stars||0) + ' &nbsp;&#9434; ' + (data.forks||0) + ' &nbsp;' + (data.language||'unknown') + '</div>' +
    '<div class="top-row"><div class="score-card">' +
    '<div class="score-number" style="color:' + gradeColor(data.overall_grade) + '">' + data.overall_score + '</div>' +
    '<div class="score-grade">' + data.overall_grade + ' &nbsp;/ 100</div></div>' +
    refreshBadge + '</div>' +
    '<div id="history-container" style="display:none" class="history-section">' +
    '<div class="section-title">Score History</div>' +
    '<canvas id="historyChart" height="80"></canvas></div>' +
    '<div class="section-title" style="margin-bottom:0.75rem">Checks</div>' +
    '<div class="checks">';

  for (const c of data.checks) {
    const details = c.details.map(d =>
      '<div class="detail-item ' + (isGood(d)?'good':'bad') + '">' + (isGood(d)?'&#10003;':'&#10007;') + ' ' + d + '</div>'
    ).join('');

    const fixes = c.score < 90 ? c.details.filter(isActionable) : [];
    const fixHtml = fixes.length ? '<div class="fix-section"><div class="fix-title">Fix checklist</div>' +
      fixes.map(f => '<label class="fix-item"><input type="checkbox"><span>' + f + '</span></label>').join('') +
      '</div>' : '';

    html += '<div class="check-card">' +
      '<div class="check-header"><span class="check-name">' + c.name + '</span>' +
      '<span class="check-score ' + c.grade + '">' + c.score + '</span></div>' +
      '<div class="bar-bg"><div class="bar-fill bar-' + c.grade + '" style="width:' + c.score + '%"></div></div>' +
      '<div class="details">' + details + '</div>' + fixHtml + '</div>';
  }

  html += '</div><footer>repocheck &mdash; <a href="https://pypi.org/project/repocheck-cli/">repocheck-cli</a></footer>';
  document.getElementById('app').innerHTML = html;
  renderHistoryChart();
}

fetch('/data').then(r => r.json()).then(renderReport);

fetch('/history').then(r => r.json()).then(runs => {
  cachedHistory = runs;
  renderHistoryChart();
});

if (watchSec > 0) {
  let remaining = watchSec;
  setInterval(() => {
    remaining--;
    const lbl = document.getElementById('refresh-label');
    if (remaining <= 0) {
      remaining = watchSec;
      if (lbl) lbl.textContent = 'Refreshing…';
      fetch('/data').then(r => r.json()).then(data => {
        renderReport(data);
        remaining = watchSec;
        const newLbl = document.getElementById('refresh-label');
        if (newLbl) newLbl.textContent = 'Refreshing every ' + watchSec + 's';
      });
    } else {
      if (lbl) lbl.textContent = 'Refreshing in ' + remaining + 's';
    }
  }, 1000);
}
</script>
</body>
</html>"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/data":
            self._send(200, "application/json", _REPORT_JSON.encode())
        elif path == "/history":
            self._send(200, "application/json", _HISTORY_JSON.encode())
        else:
            self._send(200, "text/html", HTML_TEMPLATE.encode())

    def _send(self, code: int, content_type: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # silence request logs


def serve(report_dict: dict, history: list[dict] | None = None, port: int = 5678) -> None:
    global _REPORT_JSON, _HISTORY_JSON
    _REPORT_JSON = json.dumps(report_dict)
    _HISTORY_JSON = json.dumps(history or [])

    server = HTTPServer(("127.0.0.1", port), _Handler)
    url = f"http://127.0.0.1:{port}"

    threading.Timer(0.3, lambda: webbrowser.open(url)).start()

    print(f"Dashboard running at {url}  (Ctrl+C to stop)")
    print(f"Tip: open {url}?watch=30 to auto-refresh every 30 seconds")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
