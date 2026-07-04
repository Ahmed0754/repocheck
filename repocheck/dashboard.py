"""Local web dashboard — serves a single-page HTML report."""
from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

_REPORT_JSON: str = "{}"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>repocheck dashboard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0d1117; color: #e6edf3; min-height: 100vh; padding: 2rem; }
  h1 { font-size: 1.4rem; font-weight: 600; margin-bottom: 0.25rem; }
  .meta { color: #8b949e; font-size: 0.85rem; margin-bottom: 2rem; }
  .score-card { display: inline-block; background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 1.5rem 2.5rem; margin-bottom: 2rem; text-align: center; }
  .score-number { font-size: 3.5rem; font-weight: 700; line-height: 1; }
  .score-grade { font-size: 1.2rem; color: #8b949e; margin-top: 0.25rem; }
  .checks { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; }
  .check-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1rem 1.25rem; }
  .check-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
  .check-name { font-weight: 600; font-size: 0.9rem; }
  .check-score { font-size: 1.1rem; font-weight: 700; }
  .bar-bg { background: #21262d; border-radius: 4px; height: 6px; margin-bottom: 0.75rem; }
  .bar-fill { height: 6px; border-radius: 4px; transition: width 0.6s ease; }
  .details { font-size: 0.78rem; color: #8b949e; line-height: 1.5; }
  .detail-item { padding: 0.1rem 0; }
  .detail-item.bad { color: #f85149; }
  .detail-item.good { color: #3fb950; }
  .A { color: #3fb950; } .B { color: #58a6ff; } .C { color: #d29922; } .D { color: #f0883e; } .F { color: #f85149; }
  .bar-A { background: #3fb950; } .bar-B { background: #58a6ff; } .bar-C { background: #d29922; } .bar-D { background: #f0883e; } .bar-F { background: #f85149; }
  footer { margin-top: 2rem; color: #8b949e; font-size: 0.8rem; }
</style>
</head>
<body>
<div id="app">Loading...</div>
<script>
fetch('/data').then(r => r.json()).then(data => {
  const gradeColor = g => ({'A':'#3fb950','B':'#58a6ff','C':'#d29922','D':'#f0883e','F':'#f85149'}[g] || '#8b949e');
  const isGood = d => !d.startsWith('No ') && !d.toLowerCase().includes('consider') && !d.toLowerCase().includes('no ');

  let html = `
    <h1>repocheck: ${data.repo}</h1>
    <div class="meta">★ ${data.stars || 0} &nbsp;⑂ ${data.forks || 0} &nbsp;${data.language || 'unknown'}</div>
    <div class="score-card">
      <div class="score-number" style="color:${gradeColor(data.overall_grade)}">${data.overall_score}</div>
      <div class="score-grade">${data.overall_grade} &nbsp;/ 100</div>
    </div>
    <div class="checks">`;

  for (const c of data.checks) {
    const details = c.details.map(d => {
      const good = isGood(d);
      return `<div class="detail-item ${good ? 'good' : 'bad'}">${good ? '✓' : '✗'} ${d}</div>`;
    }).join('');
    html += `
      <div class="check-card">
        <div class="check-header">
          <span class="check-name">${c.name}</span>
          <span class="check-score ${c.grade}">${c.score}</span>
        </div>
        <div class="bar-bg"><div class="bar-fill bar-${c.grade}" style="width:${c.score}%"></div></div>
        <div class="details">${details}</div>
      </div>`;
  }

  html += `</div><footer>repocheck &mdash; <a href="https://pypi.org/project/repocheck-cli/" style="color:#58a6ff">repocheck-cli</a></footer>`;
  document.getElementById('app').innerHTML = html;
});
</script>
</body>
</html>"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/data":
            body = _REPORT_JSON.encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            body = HTML_TEMPLATE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, *args):
        pass  # silence request logs


def serve(report_dict: dict, port: int = 5678) -> None:
    global _REPORT_JSON
    _REPORT_JSON = json.dumps(report_dict)

    server = HTTPServer(("127.0.0.1", port), _Handler)
    url = f"http://127.0.0.1:{port}"

    threading.Timer(0.3, lambda: webbrowser.open(url)).start()

    print(f"Dashboard running at {url}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
