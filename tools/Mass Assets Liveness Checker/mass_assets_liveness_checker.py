#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║  URL LIVENESS CHECKER — Flask Web GUI                    ║
║  Check URLs on ports 80, 443, 8080 with live console     ║
║  Usage: python3 url_checker_gui.py                       ║
║  Then open http://127.0.0.1:5001                         ║
╚══════════════════════════════════════════════════════════╝
"""
import os, sys, time, re, json, queue, threading, uuid, io
from pathlib import Path
from datetime import datetime
import concurrent.futures

try:
    import requests, urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import socket

from flask import Flask, request, jsonify, Response, send_file
app = Flask(__name__)

UPLOAD = Path("uploads"); UPLOAD.mkdir(exist_ok=True)
REPORTS = Path("reports"); REPORTS.mkdir(exist_ok=True)
JOBS = {}

# ── Check functions ──────────────────────────────────────
PORTS = [(80,"http"),(443,"https"),(8080,"http"),(8080,"https")]
PORT_LABELS = {(80,"http"):"http:// (80)",(443,"https"):"https:// (443)",
               (8080,"http"):"http:// (8080)",(8080,"https"):"https:// (8080)"}

def check_http(host, port, scheme, timeout=5):
    url = f"{scheme}://{host}" if port in (80,443) else f"{scheme}://{host}:{port}"
    try:
        r = requests.head(url, timeout=timeout, verify=False, allow_redirects=True,
                         headers={"User-Agent":"Mozilla/5.0 URLChecker/2.0"})
        return url, "ACTIVE", r.status_code, dict(r.headers)
    except requests.exceptions.ConnectTimeout: return url, "TIMEOUT", 0, {}
    except requests.exceptions.SSLError as e: return url, "SSL_ERROR", 0, {"error": str(e)[:100]}
    except requests.exceptions.ConnectionError: return url, "INACTIVE", 0, {}
    except Exception as e: return url, "ERROR", 0, {"error": str(e)[:100]}

def check_socket(host, port, scheme, timeout=3):
    url = f"{scheme}://{host}" if port in (80,443) else f"{scheme}://{host}:{port}"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout); s.connect((host, port)); s.close()
        return url, "ACTIVE", 0, {}
    except socket.timeout: return url, "TIMEOUT", 0, {}
    except (ConnectionRefusedError, OSError): return url, "INACTIVE", 0, {}
    except Exception: return url, "ERROR", 0, {}

check_fn = check_http if HAS_REQUESTS else check_socket

def load_urls(filepath):
    fp = Path(filepath)
    if fp.suffix.lower() in (".xlsx",".xls"):
        from openpyxl import load_workbook
        wb = load_workbook(str(fp), data_only=True, read_only=True)
        ws = wb.active
        urls = []
        for row in ws.iter_rows(min_col=1, max_col=1, values_only=True):
            val = str(row[0] or "").strip()
            if val and val.lower() not in ("url","hostname","host","domain") and "." in val:
                val = re.sub(r'^https?://','',val).split('/')[0].strip()
                if val: urls.append(val)
        wb.close()
        return list(dict.fromkeys(urls))
    else:
        urls = []
        with open(filepath) as f:
            for line in f:
                val = line.strip()
                if val and not val.startswith("#") and "." in val:
                    val = re.sub(r'^https?://','',val).split('/')[0].strip()
                    if val: urls.append(val)
        return list(dict.fromkeys(urls))

# ── Scan job ─────────────────────────────────────────────
def run_scan(job_id, urls, workers=30, timeout=5):
    q = JOBS[job_id]["queue"]
    results = {}
    total = len(urls) * len(PORTS)

    def emit(event, data):
        q.put(json.dumps({"event":event,"data":data}, default=str))

    emit("log", {"msg": f"Starting scan: {len(urls)} hosts × {len(PORTS)} ports = {total} checks", "level":"info"})
    emit("log", {"msg": f"Using {'HTTP HEAD requests' if HAS_REQUESTS else 'TCP socket probes'} with {workers} threads", "level":"info"})
    emit("progress", {"done":0, "total":total, "pct":0})

    start = time.time()
    done_count = 0
    live_count = 0
    down_count = 0
    lock = threading.Lock()

    for host in urls:
        results[host] = {}

    tasks = [(h, p, s) for h in urls for p, s in PORTS]

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(check_fn, h, p, s, timeout): (h, p, s) for h, p, s in tasks}
        for future in concurrent.futures.as_completed(futures):
            h, p, s = futures[future]
            url, status, code, hdrs = future.result()
            results[h][url] = {"status":status, "code":code, "headers":hdrs}

            with lock:
                done_count += 1

            icon = {"ACTIVE":"✅","INACTIVE":"❌","TIMEOUT":"⏱","SSL_ERROR":"🔒","ERROR":"💥"}.get(status,"?")
            code_str = f" ({code})" if code else ""
            level = "good" if status=="ACTIVE" else "warn" if status in ("TIMEOUT","SSL_ERROR") else "dim"
            emit("check", {"host":h, "url":url, "status":status, "code":code,
                           "icon":icon, "port":p, "scheme":s})
            emit("log", {"msg": f"{icon} {url} → {status}{code_str}", "level":level})
            emit("progress", {"done":done_count, "total":total,
                              "pct": round(done_count*100/total)})

    elapsed = time.time() - start

    # Build final results
    rows = []
    for host in urls:
        row = {"host": host, "ports": {}}
        active = 0
        for port, scheme in PORTS:
            url = f"{scheme}://{host}" if port in (80,443) else f"{scheme}://{host}:{port}"
            info = results[host].get(url, {"status":"ERROR","code":0})
            row["ports"][f"{scheme}_{port}"] = info
            if info["status"] == "ACTIVE": active += 1
        row["active_count"] = active
        row["status"] = "LIVE" if active > 0 else "DOWN"
        if row["status"] == "LIVE": live_count += 1
        else: down_count += 1
        rows.append(row)

    # Save Excel
    try:
        xlsx_path = save_excel(rows, urls, elapsed, job_id)
        JOBS[job_id]["xlsx_path"] = str(xlsx_path)
        emit("log", {"msg": f"📄 Excel report saved: {xlsx_path.name}", "level":"good"})
    except Exception as e:
        emit("log", {"msg": f"Excel save error: {e}", "level":"error"})

    emit("log", {"msg": f"\n{'═'*50}", "level":"info"})
    emit("log", {"msg": f"  SCAN COMPLETE in {elapsed:.1f}s", "level":"info"})
    emit("log", {"msg": f"  ✅ LIVE: {live_count}  |  ❌ DOWN: {down_count}  |  Total: {len(urls)}", "level":"good"})
    emit("log", {"msg": f"{'═'*50}", "level":"info"})

    emit("done", {"rows":rows, "live":live_count, "down":down_count,
                  "total":len(urls), "elapsed":round(elapsed,1),
                  "xlsx": JOBS[job_id].get("xlsx_path","")})
    q.put(None)  # sentinel

def save_excel(rows, urls, elapsed, job_id):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = Workbook(); ws = wb.active; ws.title = "URL Status"
    hf = Font(name="Arial",bold=True,color="FFFFFF",size=11)
    hfill = PatternFill("solid",fgColor="1a1a2e")
    af = Font(name="Arial",color="00BB66",size=10,bold=True)
    afl = PatternFill("solid",fgColor="E8F5E9")
    nf = Font(name="Arial",color="CC3333",size=10)
    nfl = PatternFill("solid",fgColor="FFEBEE")
    tf = Font(name="Arial",color="CC8800",size=10)
    tfl = PatternFill("solid",fgColor="FFF8E1")
    bdr = Border(bottom=Side("thin",color="DDDDDD"),right=Side("thin",color="DDDDDD"))

    hdrs = ["#","Hostname","http:// (80)","https:// (443)","http:// (8080)","https:// (8080)","Active","Status"]
    for c,h in enumerate(hdrs,1):
        cell=ws.cell(1,c,h);cell.font=hf;cell.fill=hfill;cell.alignment=Alignment(horizontal="center");cell.border=bdr

    ws.column_dimensions['A'].width=5;ws.column_dimensions['B'].width=55
    for col in 'CDEF': ws.column_dimensions[col].width=20
    ws.column_dimensions['G'].width=8;ws.column_dimensions['H'].width=8

    for i,row in enumerate(rows,1):
        r=i+1
        ws.cell(r,1,i).font=Font(name="Arial",color="999999",size=10)
        ws.cell(r,2,row["host"]).font=Font(name="Arial",color="1565C0",size=10)
        ci=3
        for port,scheme in PORTS:
            key=f"{scheme}_{port}"
            info=row["ports"].get(key,{"status":"ERROR","code":0})
            cell=ws.cell(r,ci)
            st=info["status"]
            if st=="ACTIVE": cell.value=f"ACTIVE ({info['code']})" if info['code'] else "ACTIVE";cell.font=af;cell.fill=afl
            elif st=="TIMEOUT": cell.value="TIMEOUT";cell.font=tf;cell.fill=tfl
            elif st=="SSL_ERROR": cell.value="SSL ERROR";cell.font=tf;cell.fill=tfl
            else: cell.value="INACTIVE";cell.font=nf;cell.fill=nfl
            cell.alignment=Alignment(horizontal="center");cell.border=bdr;ci+=1
        ws.cell(r,7,row["active_count"]).font=Font(name="Arial",color="00BB66" if row["active_count"] else "CC3333",bold=True,size=11)
        ws.cell(r,7).alignment=Alignment(horizontal="center")
        sc=ws.cell(r,8)
        if row["status"]=="LIVE": sc.value="LIVE";sc.font=Font(name="Arial",color="00BB66",bold=True);sc.fill=afl
        else: sc.value="DOWN";sc.font=Font(name="Arial",color="CC3333",bold=True);sc.fill=nfl
        sc.alignment=Alignment(horizontal="center")
        for c in range(1,9): ws.cell(r,c).border=bdr

    sr=len(rows)+3
    ws.cell(sr,1,"SUMMARY").font=Font(name="Arial",bold=True,color="1565C0",size=12)
    live=sum(1 for r in rows if r["status"]=="LIVE")
    ws.cell(sr,2,f"Total: {len(rows)} | Live: {live} | Down: {len(rows)-live} | Time: {elapsed:.1f}s").font=Font(name="Arial",size=11)
    ws.freeze_panes="A2"; ws.auto_filter.ref=f"A1:H{len(rows)+1}"

    out = REPORTS / f"url_check_{job_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb.save(str(out))
    return out

# ── Flask Routes ─────────────────────────────────────────
@app.route("/")
def index():
    return HTML_PAGE

@app.route("/api/scan", methods=["POST"])
def start_scan():
    job_id = uuid.uuid4().hex[:12]
    workers = int(request.form.get("workers", 30))
    timeout = int(request.form.get("timeout", 5))

    # Get URLs from file or textarea
    urls = []
    f = request.files.get("file")
    if f and f.filename:
        fp = UPLOAD / f"{job_id}_{f.filename}"
        f.save(str(fp))
        urls = load_urls(str(fp))

    text_urls = request.form.get("urls","").strip()
    if text_urls:
        for line in text_urls.split("\n"):
            val = line.strip()
            if val and "." in val:
                val = re.sub(r'^https?://','',val).split('/')[0].strip()
                if val: urls.append(val)

    urls = list(dict.fromkeys(urls))
    if not urls:
        return jsonify({"error":"No URLs provided"}), 400

    JOBS[job_id] = {"queue": queue.Queue(), "status":"running"}
    threading.Thread(target=run_scan, args=(job_id, urls, workers, timeout), daemon=True).start()
    return jsonify({"job_id": job_id, "count": len(urls)})

@app.route("/api/stream/<job_id>")
def stream(job_id):
    if job_id not in JOBS:
        return jsonify({"error":"Job not found"}), 404
    def generate():
        q = JOBS[job_id]["queue"]
        while True:
            try:
                msg = q.get(timeout=120)
                if msg is None:
                    yield f"data: {json.dumps({'event':'end'})}\n\n"
                    break
                yield f"data: {msg}\n\n"
            except:
                yield f"data: {json.dumps({'event':'keepalive'})}\n\n"
    return Response(generate(), mimetype="text/event-stream",
                   headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@app.route("/api/download/<job_id>")
def download(job_id):
    if job_id not in JOBS: return jsonify({"error":"not found"}),404
    xlsx = JOBS[job_id].get("xlsx_path")
    if xlsx and Path(xlsx).exists():
        return send_file(xlsx, as_attachment=True, download_name=Path(xlsx).name)
    return jsonify({"error":"Report not ready"}), 404

# ── HTML Page ────────────────────────────────────────────
HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>URL Liveness Checker</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#0a0a0f; --bg2:#12121a; --bg3:#1a1a28; --bg4:#22222e;
  --text:#e0e0e8; --dim:#6a6a7a; --border:#2a2a3a;
  --green:#00e87b; --red:#ff4455; --orange:#ffaa22; --blue:#00c8ff;
  --purple:#b480ff; --surface:#16161f;
  --font:'JetBrains Mono',monospace; --sans:'DM Sans',sans-serif;
}
body{background:var(--bg);color:var(--text);font-family:var(--sans);min-height:100vh}

.app{max-width:1200px;margin:0 auto;padding:20px}

/* Header */
.header{text-align:center;padding:30px 0 20px;position:relative}
.header h1{font-family:var(--font);font-size:24px;font-weight:700;letter-spacing:2px;
  background:linear-gradient(135deg,var(--green),var(--blue));-webkit-background-clip:text;
  -webkit-text-fill-color:transparent;margin-bottom:4px}
.header .sub{font-size:12px;color:var(--dim);letter-spacing:1px}

/* Upload Section */
.upload-section{background:var(--bg2);border:1px solid var(--border);border-radius:12px;
  padding:24px;margin-bottom:16px}
.upload-section h2{font-size:14px;color:var(--blue);margin-bottom:12px;font-family:var(--font)}
.upload-row{display:flex;gap:12px;align-items:flex-start;flex-wrap:wrap}
.upload-box{flex:1;min-width:250px}
.upload-box label{font-size:11px;color:var(--dim);text-transform:uppercase;letter-spacing:1px;
  display:block;margin-bottom:6px}
.upload-box textarea{width:100%;height:120px;background:var(--bg);border:1px solid var(--border);
  border-radius:8px;padding:10px;color:var(--text);font-family:var(--font);font-size:11px;resize:vertical}
.upload-box textarea:focus{outline:none;border-color:var(--blue)}
.upload-box input[type=file]{width:100%;padding:10px;background:var(--bg);border:2px dashed var(--border);
  border-radius:8px;color:var(--dim);font-size:11px;cursor:pointer}
.upload-box input[type=file]:hover{border-color:var(--blue)}
.config-row{display:flex;gap:12px;margin-top:12px;align-items:center}
.config-row label{font-size:10px;color:var(--dim)}
.config-row input[type=number]{width:60px;padding:4px 8px;background:var(--bg);border:1px solid var(--border);
  border-radius:6px;color:var(--text);font-family:var(--font);font-size:11px;text-align:center}
.btn-scan{padding:10px 30px;background:linear-gradient(135deg,var(--green),#00b86e);color:#000;
  border:none;border-radius:8px;font-family:var(--font);font-size:13px;font-weight:700;
  cursor:pointer;letter-spacing:1px;transition:all .2s;margin-left:auto}
.btn-scan:hover{transform:translateY(-1px);box-shadow:0 4px 20px rgba(0,232,123,.3)}
.btn-scan:disabled{opacity:.4;cursor:not-allowed;transform:none;box-shadow:none}
.btn-scan.running{background:linear-gradient(135deg,var(--red),#cc3344);color:#fff}

/* Stats Bar */
.stats-bar{display:flex;gap:8px;margin-bottom:16px}
.stat-card{flex:1;background:var(--bg2);border:1px solid var(--border);border-radius:10px;
  padding:14px;text-align:center}
.stat-card .val{font-family:var(--font);font-size:28px;font-weight:700}
.stat-card .lbl{font-size:9px;color:var(--dim);text-transform:uppercase;letter-spacing:1.5px;margin-top:2px}
.stat-live .val{color:var(--green)} .stat-down .val{color:var(--red)}
.stat-total .val{color:var(--blue)} .stat-time .val{color:var(--orange)}

/* Progress */
.progress-wrap{background:var(--bg2);border:1px solid var(--border);border-radius:10px;
  padding:12px 16px;margin-bottom:16px;display:none}
.progress-bar{height:6px;background:var(--bg);border-radius:3px;overflow:hidden;margin-bottom:6px}
.progress-fill{height:100%;background:linear-gradient(90deg,var(--green),var(--blue));
  width:0%;transition:width .3s;border-radius:3px}
.progress-text{font-size:10px;color:var(--dim);font-family:var(--font);display:flex;justify-content:space-between}

/* Results Table */
.results-section{background:var(--bg2);border:1px solid var(--border);border-radius:12px;
  overflow:hidden;margin-bottom:16px;display:none}
.results-header{padding:14px 18px;border-bottom:1px solid var(--border);display:flex;
  align-items:center;gap:10px}
.results-header h2{font-size:14px;color:var(--blue);font-family:var(--font)}
.filter-btns{display:flex;gap:4px;margin-left:auto}
.filter-btn{padding:3px 10px;font-size:10px;background:var(--bg);border:1px solid var(--border);
  border-radius:20px;color:var(--dim);cursor:pointer;font-family:var(--font)}
.filter-btn.active{background:var(--blue);color:#000;border-color:var(--blue)}
.filter-btn:hover{border-color:var(--blue)}
table{width:100%;border-collapse:collapse}
th{background:var(--bg3);font-size:10px;color:var(--dim);text-transform:uppercase;letter-spacing:1px;
  padding:8px 12px;text-align:center;font-family:var(--font);font-weight:600;
  border-bottom:1px solid var(--border);position:sticky;top:0}
th:nth-child(2){text-align:left}
td{padding:6px 12px;border-bottom:1px solid rgba(255,255,255,.03);font-size:11px;text-align:center;
  font-family:var(--font)}
td:nth-child(2){text-align:left;color:var(--blue)}
tr:hover{background:rgba(0,200,255,.03)}
.s-active{color:var(--green);font-weight:600}
.s-inactive{color:var(--red)}
.s-timeout{color:var(--orange)}
.s-ssl{color:var(--orange)}
.s-live{color:var(--green);font-weight:700}
.s-down{color:var(--red);font-weight:700}
.tbl-wrap{max-height:60vh;overflow-y:auto}
.dl-btn{padding:6px 14px;background:var(--green);color:#000;border:none;border-radius:6px;
  font-family:var(--font);font-size:11px;font-weight:600;cursor:pointer;display:none}
.dl-btn:hover{background:#00ff88}

/* Console */
.console-section{background:var(--bg2);border:1px solid var(--border);border-radius:12px;
  overflow:hidden;margin-bottom:16px}
.console-header{padding:10px 16px;border-bottom:1px solid var(--border);display:flex;
  align-items:center;gap:8px}
.console-header h2{font-size:13px;color:var(--purple);font-family:var(--font)}
.console-header .live{font-size:9px;color:var(--green);display:none;animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.console-body{height:300px;overflow-y:auto;padding:10px 14px;background:var(--bg);font-family:var(--font);font-size:10px;line-height:1.7}
.log-good{color:var(--green)} .log-warn{color:var(--orange)} .log-error{color:var(--red)}
.log-info{color:var(--dim)} .log-dim{color:#444}
.clear-btn{margin-left:auto;padding:3px 10px;font-size:9px;background:var(--bg);border:1px solid var(--border);
  border-radius:4px;color:var(--dim);cursor:pointer;font-family:var(--font)}
</style>
</head>
<body>
<div class="app">

<div class="header">
  <h1>⬡ URL LIVENESS CHECKER</h1>
  <div class="sub">CHECK PORTS 80 · 443 · 8080 WITH LIVE CONSOLE</div>
</div>

<div class="upload-section">
  <h2>📋 Input URLs</h2>
  <div class="upload-row">
    <div class="upload-box">
      <label>Paste URLs (one per line)</label>
      <textarea id="url-text" placeholder="example.com&#10;api.example.com&#10;staging.example.com"></textarea>
    </div>
    <div class="upload-box">
      <label>Or upload file (.txt / .xlsx)</label>
      <input type="file" id="url-file" accept=".txt,.csv,.xlsx,.xls">
      <div id="file-tag" style="margin-top:6px;font-size:10px;color:var(--dim)"></div>
    </div>
  </div>
  <div class="config-row">
    <label>Threads:</label>
    <input type="number" id="cfg-workers" value="30" min="1" max="100">
    <label>Timeout (s):</label>
    <input type="number" id="cfg-timeout" value="5" min="1" max="30">
    <button class="btn-scan" id="scan-btn" onclick="startScan()">▶ START SCAN</button>
  </div>
</div>

<div class="stats-bar">
  <div class="stat-card stat-total"><div class="val" id="st-total">—</div><div class="lbl">Total Hosts</div></div>
  <div class="stat-card stat-live"><div class="val" id="st-live">—</div><div class="lbl">Live</div></div>
  <div class="stat-card stat-down"><div class="val" id="st-down">—</div><div class="lbl">Down</div></div>
  <div class="stat-card stat-time"><div class="val" id="st-time">—</div><div class="lbl">Seconds</div></div>
</div>

<div class="progress-wrap" id="progress-wrap">
  <div class="progress-bar"><div class="progress-fill" id="progress-fill"></div></div>
  <div class="progress-text">
    <span id="progress-label">Starting…</span>
    <span id="progress-pct">0%</span>
  </div>
</div>

<div class="results-section" id="results-section">
  <div class="results-header">
    <h2>📊 Results</h2>
    <div class="filter-btns">
      <span class="filter-btn active" onclick="filterResults('all',this)">All</span>
      <span class="filter-btn" onclick="filterResults('LIVE',this)">✅ Live</span>
      <span class="filter-btn" onclick="filterResults('DOWN',this)">❌ Down</span>
    </div>
    <button class="dl-btn" id="dl-btn" onclick="downloadXlsx()">⬇ Download Excel</button>
  </div>
  <div class="tbl-wrap">
    <table>
      <thead><tr>
        <th>#</th><th>Hostname</th><th>http (80)</th><th>https (443)</th>
        <th>http (8080)</th><th>https (8080)</th><th>Active</th><th>Status</th>
      </tr></thead>
      <tbody id="results-body"></tbody>
    </table>
  </div>
</div>

<div class="console-section">
  <div class="console-header">
    <h2>🖥 Console</h2>
    <span class="live" id="live-badge">● LIVE</span>
    <button class="clear-btn" onclick="document.getElementById('console').innerHTML=''">✕ Clear</button>
  </div>
  <div class="console-body" id="console">
    <div class="log-dim">Ready. Upload URLs or paste them above.</div>
  </div>
</div>

</div>

<script>
let _jobId=null, _rows=[], _filter='all';

document.getElementById('url-file').onchange=function(){
  const f=this.files[0];
  document.getElementById('file-tag').textContent=f?`✓ ${f.name} (${(f.size/1024).toFixed(1)}KB)`:'';
};

function addLog(msg, level='info'){
  const el=document.getElementById('console');
  const div=document.createElement('div');
  div.className='log-'+level;
  const ts=new Date().toLocaleTimeString();
  div.textContent=`[${ts}] ${msg}`;
  el.appendChild(div);
  el.scrollTop=el.scrollHeight;
}

function startScan(){
  const btn=document.getElementById('scan-btn');
  if(btn.classList.contains('running')){return;}

  const fd=new FormData();
  const text=document.getElementById('url-text').value.trim();
  if(text) fd.append('urls',text);
  const file=document.getElementById('url-file').files[0];
  if(file) fd.append('file',file);
  fd.append('workers',document.getElementById('cfg-workers').value);
  fd.append('timeout',document.getElementById('cfg-timeout').value);

  if(!text&&!file){addLog('Please provide URLs','error');return;}

  btn.disabled=true;btn.classList.add('running');btn.textContent='⏹ SCANNING…';
  document.getElementById('progress-wrap').style.display='block';
  document.getElementById('live-badge').style.display='inline';
  document.getElementById('results-section').style.display='block';
  document.getElementById('results-body').innerHTML='';
  document.getElementById('dl-btn').style.display='none';
  _rows=[];

  document.getElementById('console').innerHTML='';
  addLog('Uploading URLs…','info');

  fetch('/api/scan',{method:'POST',body:fd})
  .then(r=>r.json()).then(data=>{
    if(data.error){addLog('Error: '+data.error,'error');resetBtn();return;}
    _jobId=data.job_id;
    addLog(`Job ${_jobId}: ${data.count} hosts queued`,'info');
    connectSSE(_jobId);
  }).catch(e=>{addLog('Upload failed: '+e,'error');resetBtn();});
}

function resetBtn(){
  const btn=document.getElementById('scan-btn');
  btn.disabled=false;btn.classList.remove('running');btn.textContent='▶ START SCAN';
  document.getElementById('live-badge').style.display='none';
}

function connectSSE(jobId){
  const es=new EventSource('/api/stream/'+jobId);
  es.onmessage=e=>{
    try{
      const msg=JSON.parse(e.data);
      handleEvent(msg);
      if(msg.event==='end') es.close();
    }catch(ex){}
  };
  es.onerror=()=>{addLog('Connection lost','error');es.close();resetBtn();};
}

function handleEvent(msg){
  const {event,data}=msg;
  if(event==='log') addLog(data.msg, data.level);
  else if(event==='progress'){
    document.getElementById('progress-fill').style.width=data.pct+'%';
    document.getElementById('progress-label').textContent=`${data.done} / ${data.total} checked`;
    document.getElementById('progress-pct').textContent=data.pct+'%';
  }
  else if(event==='done'){
    _rows=data.rows||[];
    document.getElementById('st-total').textContent=data.total;
    document.getElementById('st-live').textContent=data.live;
    document.getElementById('st-down').textContent=data.down;
    document.getElementById('st-time').textContent=data.elapsed+'s';
    document.getElementById('dl-btn').style.display='inline-block';
    renderTable();
    resetBtn();
  }
}

function renderTable(){
  const tbody=document.getElementById('results-body');
  const filtered=_filter==='all'?_rows:_rows.filter(r=>r.status===_filter);
  tbody.innerHTML=filtered.map((r,i)=>{
    const portCells=[['http_80'],['https_443'],['http_8080'],['https_8080']].map(([key])=>{
      const info=r.ports[key]||{status:'ERROR',code:0};
      const cls={ACTIVE:'s-active',INACTIVE:'s-inactive',TIMEOUT:'s-timeout',SSL_ERROR:'s-ssl'}[info.status]||'s-inactive';
      const label=info.status==='ACTIVE'?(info.code?`ACTIVE (${info.code})`:'ACTIVE'):info.status.replace('_',' ');
      return `<td class="${cls}">${label}</td>`;
    }).join('');
    return `<tr>
      <td style="color:var(--dim)">${i+1}</td>
      <td>${r.host}</td>
      ${portCells}
      <td style="color:${r.active_count?'var(--green)':'var(--red)'};font-weight:700">${r.active_count}</td>
      <td class="s-${r.status.toLowerCase()}">${r.status}</td>
    </tr>`;
  }).join('');
}

function filterResults(f,btn){
  _filter=f;
  document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
  if(btn)btn.classList.add('active');
  renderTable();
}

function downloadXlsx(){
  if(!_jobId)return;
  window.location.href='/api/download/'+_jobId;
}
</script>
</body>
</html>"""

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════╗")
    print("║  URL LIVENESS CHECKER — http://127.0.0.1:5001 ║")
    print("╚══════════════════════════════════════════════╝")
    app.run(host="0.0.0.0", port=5001, debug=False, threaded=True)
