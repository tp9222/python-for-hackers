import os
import re
import json
import time
import uuid
import threading
from queue import PriorityQueue
from datetime import datetime
from urllib.parse import urljoin, urlparse, unquote
from flask import Flask, render_template_string, request, jsonify, Response
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0"})

DOWNLOAD_ROOT = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_ROOT, exist_ok=True)

JOBS = {}


def same_host(a, b):
    return urlparse(a).netloc == urlparse(b).netloc


_SIZE_RE = re.compile(r"^([\d.]+)\s*([KMGTP]?)i?B?$", re.I)
_UNITS = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4, "P": 1024**5}
_DATE_FMTS = [
    "%d-%b-%Y %H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S",
    "%d-%b-%Y %H:%M:%S", "%d-%m-%Y %H:%M", "%b %d %Y %H:%M",
]


def parse_size(tok):
    tok = tok.strip()
    if not tok or tok == "-":
        return None
    m = _SIZE_RE.match(tok)
    if not m:
        try:
            return int(tok.replace(",", ""))
        except ValueError:
            return None
    num, unit = m.group(1), m.group(2).upper()
    try:
        return int(float(num) * _UNITS.get(unit, 1))
    except ValueError:
        return None


def parse_date(text):
    text = text.strip()
    m = re.search(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?", text)
    if not m:
        m = re.search(r"\d{1,2}-[A-Za-z]{3}-\d{4}\s+\d{2}:\d{2}(:\d{2})?", text)
    cand = m.group(0).replace("T", " ") if m else text
    for fmt in _DATE_FMTS:
        try:
            return datetime.strptime(cand, fmt).timestamp()
        except ValueError:
            continue
    return None


def extract_meta(anchor):
    tail = ""
    sib = anchor.next_sibling
    while sib is not None:
        if getattr(sib, "name", None) is not None:
            if sib.name == "a" or sib.find("a"):
                break
            tail += sib.get_text()
        else:
            tail += str(sib)
        if "\n" in tail:
            tail = tail.split("\n", 1)[0]
            break
        sib = sib.next_sibling
    tail = re.sub(r"\s+", " ", tail).strip()
    mtime = parse_date(tail)
    size = None
    for tok in reversed(tail.split()):
        s = parse_size(tok)
        if s is not None:
            size = s
            break
    if mtime is None and size is None:
        tr = anchor.find_parent("tr")
        if tr:
            cells = [re.sub(r"\s+", " ", td.get_text()).strip() for td in tr.find_all("td")]
            for c in cells:
                if mtime is None:
                    mtime = parse_date(c)
                if size is None:
                    s = parse_size(c)
                    if s is not None:
                        size = s
    return size, mtime


def list_dir(url):
    if not url.endswith("/"):
        url += "/"
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    base_path = urlparse(url).path
    entries, seen = [], set()
    for a in soup.find_all("a"):
        href = a.get("href")
        if not href or href.startswith(("?", "#")):
            continue
        if href in ("../", ".."):
            continue
        full = urljoin(url, href)
        if not full.startswith(("http://", "https://")):
            continue
        if not same_host(full, url):
            continue
        fp = urlparse(full).path
        if fp == base_path or not fp.startswith(base_path):
            continue
        if full in seen:
            continue
        seen.add(full)
        is_dir = href.endswith("/")
        name = unquote(href.rstrip("/").split("/")[-1])
        if name:
            size, mtime = (None, None) if is_dir else extract_meta(a)
            if is_dir:
                _, mtime = extract_meta(a)
            entries.append({"name": name, "url": full, "is_dir": is_dir,
                            "size": size, "mtime": mtime})
    entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
    return entries


def collect_files(url, rel, acc, stop):
    if stop.is_set():
        return
    for e in list_dir(url):
        if stop.is_set():
            return
        child_rel = os.path.join(rel, e["name"])
        if e["is_dir"]:
            collect_files(e["url"], child_rel, acc, stop)
        else:
            acc.append((e["url"], child_rel))


def _now():
    return time.monotonic()


def _calc_speed(samples):
    if len(samples) < 2:
        return 0.0
    t0, b0 = samples[0]
    t1, b1 = samples[-1]
    dt = t1 - t0
    return (b1 - b0) / dt if dt > 0 else 0.0


SEGMENT_THRESHOLD = 4 * 1024 * 1024
SEGMENT_MIN = 1 * 1024 * 1024


def _probe(url):
    try:
        h = SESSION.head(url, timeout=30, allow_redirects=True)
        size = int(h.headers.get("Content-Length", 0))
        ranges = h.headers.get("Accept-Ranges", "").lower() == "bytes"
        if size > 0:
            return size, ranges
    except Exception:
        pass
    try:
        g = SESSION.get(url, stream=True, timeout=30,
                        headers={"Range": "bytes=0-0"})
        if g.status_code == 206:
            cr = g.headers.get("Content-Range", "")
            total = int(cr.split("/")[-1]) if "/" in cr else 0
            g.close()
            return total, True
        size = int(g.headers.get("Content-Length", 0))
        g.close()
        return size, False
    except Exception:
        return 0, False


def _download_segment(url, start, end, fh, fh_lock, item, job, stop):
    headers = {"Range": f"bytes={start}-{end}"}
    pos = start
    with SESSION.get(url, stream=True, timeout=120, headers=headers) as r:
        r.raise_for_status()
        for chunk in r.iter_content(65536):
            if stop.is_set():
                return False
            p = job.get("pause")
            while p is not None and p.is_set() and not stop.is_set():
                time.sleep(0.2)
            if not chunk:
                continue
            with fh_lock:
                fh.seek(pos)
                fh.write(chunk)
            pos += len(chunk)
            item["bytes"] += len(chunk)
            job["bytes"] += len(chunk)
    return True


def download_file(url, dest, item, job, stop, conns):
    tmp = dest + ".part"
    size, ranges = _probe(url) if conns > 1 else (0, False)
    segmented = ranges and size >= SEGMENT_THRESHOLD and conns > 1
    if segmented:
        n = min(conns, max(1, size // SEGMENT_MIN))
        seg = size // n
        bounds = []
        for i in range(n):
            s = i * seg
            e = size - 1 if i == n - 1 else (s + seg - 1)
            bounds.append((s, e))
        with open(tmp, "wb") as fh:
            fh.truncate(size)
        fh = open(tmp, "r+b")
        fh_lock = threading.Lock()
        errors = []

        def run_seg(s, e):
            try:
                if not _download_segment(url, s, e, fh, fh_lock, item, job, stop):
                    errors.append("interrupted")
            except Exception as ex:
                errors.append(str(ex))

        threads = [threading.Thread(target=run_seg, args=(s, e), daemon=True) for s, e in bounds]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        fh.close()
        if stop.is_set() or errors:
            if os.path.exists(tmp):
                os.remove(tmp)
            if errors and not stop.is_set():
                raise RuntimeError(errors[0])
            return False
        os.replace(tmp, dest)
        return True
    # single-stream fallback
    with SESSION.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(tmp, "wb") as fh:
            for chunk in r.iter_content(65536):
                if stop.is_set():
                    break
                p = job.get("pause")
                while p is not None and p.is_set() and not stop.is_set():
                    time.sleep(0.2)
                if chunk:
                    fh.write(chunk)
                    item["bytes"] += len(chunk)
                    job["bytes"] += len(chunk)
    if stop.is_set():
        if os.path.exists(tmp):
            os.remove(tmp)
        return False
    os.replace(tmp, dest)
    return True


def run_job(job_id, folders, dest_base, workers):
    job = JOBS[job_id]
    stop = job["stop"]
    pq = job["queue"]
    seq = [0]
    seq_lock = threading.Lock()

    def scan(f):
        item = job["items"][f["id"]]
        try:
            files = []
            collect_files(f["url"], f["name"], files, stop)
            item["total"] = len(files)
            if not files:
                item["total"] = 1
                item["done"] = 1
                item["status"] = "done"
                return
            item["status"] = "queued"
            for u, rel in files:
                fname = os.path.relpath(rel, f["name"]) if rel.startswith(f["name"] + os.sep) else os.path.basename(rel)
                if rel in item["_done_files"] or os.path.exists(os.path.join(dest_base, rel)):
                    item["files"][fname] = "done"
                else:
                    item["files"].setdefault(fname, "queued")
                with seq_lock:
                    n = seq[0]
                    seq[0] += 1
                pq.put((job["prio"].get(f["id"], 100), n, f["id"], u, rel))
        except Exception as e:
            item["status"] = "error"
            item["errors"].append(str(e))

    scan_threads = [threading.Thread(target=scan, args=(f,), daemon=True) for f in folders]
    for t in scan_threads:
        t.start()

    def worker():
        while True:
            if stop.is_set():
                return
            pause = job.get("pause")
            if pause is not None:
                while pause.is_set() and not stop.is_set():
                    time.sleep(0.2)
            if stop.is_set():
                return
            try:
                prio, n, fid, url, rel = pq.get(timeout=0.3)
            except Exception:
                if all(not t.is_alive() for t in scan_threads) and pq.empty():
                    return
                continue
            item = job["items"][fid]
            if item["status"] in ("queued", "scanning"):
                item["status"] = "downloading"
            dest = os.path.join(dest_base, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            fname = os.path.relpath(rel, item["name"]) if rel.startswith(item["name"] + os.sep) else os.path.basename(rel)
            if rel in item["_done_files"] or (os.path.exists(dest) and os.path.getsize(dest) > 0):
                item["_done_files"].add(rel)
                item["files"][fname] = "done"
                item["done"] += 1
                pq.task_done()
                continue
            item["files"][fname] = "downloading"
            ok = False
            try:
                ok = download_file(url, dest, item, job, stop, job.get("conns", 1))
            except Exception as e:
                item["errors"].append(f"{rel}: {e}")
            if ok:
                item["_done_files"].add(rel)
                item["files"][fname] = "done"
            else:
                item["files"][fname] = "stopped" if stop.is_set() else "error"
            item["done"] += 1
            pq.task_done()

    pool = [threading.Thread(target=worker, daemon=True) for _ in range(max(1, workers))]
    for t in pool:
        t.start()

    def sampler():
        while not job["finished"]:
            now = _now()
            for item in job["items"].values():
                item["_samp"].append((now, item["bytes"]))
                if len(item["_samp"]) > 12:
                    item["_samp"].pop(0)
                item["speed"] = _calc_speed(item["_samp"])
            job["_samp"].append((now, job["bytes"]))
            if len(job["_samp"]) > 12:
                job["_samp"].pop(0)
            job["speed"] = _calc_speed(job["_samp"])
            time.sleep(0.5)
    threading.Thread(target=sampler, daemon=True).start()

    for t in scan_threads:
        t.join()
    for t in pool:
        t.join()

    for item in job["items"].values():
        if item["status"] in ("downloading", "queued", "scanning"):
            if stop.is_set():
                item["status"] = "stopped"
            else:
                item["status"] = "done" if not item["errors"] else "partial"
        item["speed"] = 0.0
    job["speed"] = 0.0
    job["finished"] = True


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/api/list", methods=["POST"])
def api_list():
    url = (request.json or {}).get("url", "").strip()
    if not url:
        return jsonify({"error": "URL required"}), 400
    try:
        return jsonify({"entries": list_dir(url)})
    except Exception as e:
        return jsonify({"error": str(e)}), 502


def _start_job(folders, workers, dest_base, resume_state=None, conns=1):
    job_id = uuid.uuid4().hex
    os.makedirs(dest_base, exist_ok=True)
    items = {}
    prio = {}
    rs_items = (resume_state or {}).get("items", {})
    for idx, f in enumerate(folders):
        f["id"] = f.get("id") or uuid.uuid4().hex
        prio[f["id"]] = f.get("prio", idx)
        done_files = set(rs_items.get(f["id"], {}).get("done_files", []))
        items[f["id"]] = {
            "name": f["name"], "total": 0, "done": 0, "status": "scanning",
            "errors": [], "bytes": 0, "speed": 0.0, "prio": prio[f["id"]],
            "_samp": [], "_done_files": done_files, "url": f["url"], "files": {},
        }
    JOBS[job_id] = {
        "items": items, "stop": threading.Event(), "pause": threading.Event(),
        "finished": False, "dest": dest_base, "queue": PriorityQueue(),
        "prio": prio, "bytes": 0, "speed": 0.0, "_samp": [], "workers": workers,
        "conns": max(1, min(16, conns)),
        "folders": [{"id": f["id"], "name": f["name"], "url": f["url"],
                     "prio": prio[f["id"]]} for f in folders],
    }
    threading.Thread(target=run_job, args=(job_id, folders, dest_base, workers), daemon=True).start()
    return job_id, dest_base


def _resolve_dest(raw, job_id):
    raw = (raw or "").strip()
    if not raw:
        return os.path.join(DOWNLOAD_ROOT, job_id)
    return os.path.abspath(os.path.expanduser(raw))


@app.route("/api/download", methods=["POST"])
def api_download():
    data = request.json or {}
    folders = data.get("folders", [])
    workers = max(1, min(16, int(data.get("workers", 4))))
    conns = max(1, min(16, int(data.get("conns", 1))))
    if not folders:
        return jsonify({"error": "No folders selected"}), 400
    tmp_id = uuid.uuid4().hex
    dest_base = _resolve_dest(data.get("dest"), tmp_id)
    try:
        job_id, dest_base = _start_job(folders, workers, dest_base, conns=conns)
    except OSError as e:
        return jsonify({"error": f"bad download path: {e}"}), 400
    return jsonify({"job_id": job_id, "dest": dest_base})


@app.route("/api/resume", methods=["POST"])
def api_resume():
    data = request.json or {}
    state = data.get("state") or {}
    folders = state.get("folders", [])
    workers = max(1, min(16, int(data.get("workers", state.get("workers", 4)))))
    conns = max(1, min(16, int(data.get("conns", state.get("conns", 1)))))
    if not folders:
        return jsonify({"error": "Invalid session file"}), 400
    dest_base = _resolve_dest(data.get("dest") or state.get("dest"), uuid.uuid4().hex)
    try:
        job_id, dest_base = _start_job(folders, workers, dest_base, resume_state=state, conns=conns)
    except OSError as e:
        return jsonify({"error": f"bad download path: {e}"}), 400
    return jsonify({"job_id": job_id, "dest": dest_base})


@app.route("/api/session/<job_id>")
def api_session(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "unknown job"}), 404
    state = {
        "version": 1,
        "dest": job["dest"],
        "workers": job["workers"],
        "conns": job.get("conns", 1),
        "folders": job["folders"],
        "items": {
            fid: {
                "name": it["name"], "total": it["total"], "done": it["done"],
                "status": it["status"], "done_files": sorted(it["_done_files"]),
            } for fid, it in job["items"].items()
        },
    }
    return Response(json.dumps(state, indent=2), mimetype="application/json",
                    headers={"Content-Disposition": f"attachment; filename=snatchdir-session-{job_id[:8]}.json"})


@app.route("/api/priority/<job_id>", methods=["POST"])
def api_priority(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "unknown job"}), 404
    order = (request.json or {}).get("order", [])
    for rank, fid in enumerate(order):
        job["prio"][fid] = rank
        if fid in job["items"]:
            job["items"][fid]["prio"] = rank
    return jsonify({"ok": True})


@app.route("/api/pause/<job_id>", methods=["POST"])
def api_pause(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "unknown job"}), 404
    paused = (request.json or {}).get("paused", True)
    if paused:
        job["pause"].set()
    else:
        job["pause"].clear()
    return jsonify({"ok": True, "paused": paused})


@app.route("/api/progress/<job_id>")
def api_progress(job_id):
    def stream():
        while True:
            job = JOBS.get(job_id)
            if not job:
                yield f"data: {json.dumps({'error': 'unknown job'})}\n\n"
                return
            items = {
                k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")}
                for k, v in job["items"].items()
            }
            payload = {
                "items": items, "finished": job["finished"],
                "speed": job["speed"], "bytes": job["bytes"],
                "paused": job["pause"].is_set(),
            }
            yield f"data: {json.dumps(payload)}\n\n"
            if job["finished"]:
                return
            time.sleep(0.4)
    return Response(stream(), mimetype="text/event-stream")


@app.route("/api/stop/<job_id>", methods=["POST"])
def api_stop(job_id):
    job = JOBS.get(job_id)
    if job:
        job["stop"].set()
    return jsonify({"ok": True})


PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SnatchDir — HTTP Directory Fetcher</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0e1117;--panel:#161b24;--panel-2:#1c2230;--line:#262d3b;
  --ink:#e6e9ef;--mut:#8a93a6;--dim:#5a6478;
  --amber:#f0a04b;--amber-soft:#f0a04b22;--amber-line:#f0a04b55;
  --grn:#5fd09c;--red:#f06b6b;--blu:#6ba8f0;--rad:10px;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{background:var(--bg);color:var(--ink);font-family:'Space Grotesk',system-ui,sans-serif;
  font-size:14px;line-height:1.5;background-image:radial-gradient(circle at 88% -8%,#f0a04b14,transparent 42%);}
.mono{font-family:'JetBrains Mono',monospace}
.wrap{max-width:1240px;margin:0 auto;padding:28px 24px 60px}
header{display:flex;align-items:baseline;gap:14px;margin-bottom:22px}
.logo{font-weight:700;font-size:22px;letter-spacing:-.5px}
.logo b{color:var(--amber)}
.tag{color:var(--dim);font-size:12.5px;font-family:'JetBrains Mono',monospace}
.tag::before{content:"// "}
.bar{display:flex;gap:10px;background:var(--panel);border:1px solid var(--line);border-radius:var(--rad);padding:10px;align-items:center;margin-bottom:18px}
.bar .pfx{color:var(--dim);font-family:'JetBrains Mono',monospace;padding-left:8px;user-select:none}
#url{flex:1;background:transparent;border:none;outline:none;color:var(--ink);font-family:'JetBrains Mono',monospace;font-size:14px}
#url::placeholder{color:var(--dim)}
.btn{background:var(--panel-2);color:var(--ink);border:1px solid var(--line);padding:9px 16px;border-radius:8px;cursor:pointer;font-family:inherit;font-weight:600;font-size:13px;transition:.15s;white-space:nowrap}
.btn:hover{border-color:var(--amber-line);color:var(--amber)}
.btn:disabled{opacity:.4;cursor:not-allowed}
.btn.primary{background:var(--amber);color:#1a1206;border-color:var(--amber)}
.btn.primary:hover{filter:brightness(1.08);color:#1a1206}
.btn.ghost-red:hover{border-color:#f06b6b66;color:var(--red)}
.cols{display:grid;grid-template-columns:1fr 380px;gap:18px;align-items:start}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--rad);overflow:hidden}
.card-h{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;border-bottom:1px solid var(--line)}
.card-h h2{font-size:12px;text-transform:uppercase;letter-spacing:1.4px;color:var(--mut);font-weight:600}
.card-h .meta{font-size:12px;color:var(--dim);font-family:'JetBrains Mono',monospace}
.hd-right{display:flex;align-items:center;gap:12px}
.sortsel{background:var(--panel-2);color:var(--ink);border:1px solid var(--line);border-radius:7px;padding:5px 8px;font-size:11.5px;cursor:pointer;outline:none}
.sortsel:hover{border-color:var(--amber-line)}
.searchbox{background:var(--panel-2);color:var(--ink);border:1px solid var(--line);border-radius:7px;padding:5px 9px;font-size:12px;outline:none;width:150px}
.searchbox:focus{border-color:var(--amber-line)}
.searchbox::placeholder{color:var(--dim)}
.row.hide,.kids.hide{display:none!important}
.nm mark{background:var(--amber);color:#1a1206;border-radius:2px;padding:0 1px}
.meta-cols{flex:0 0 auto;display:flex;gap:14px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--dim);margin-left:auto;padding-left:10px}
.meta-cols .sz{width:64px;text-align:right}
.meta-cols .dt{width:104px;text-align:right}
.row .nm{flex:1 1 auto}
.boost{display:flex;align-items:center;gap:4px;font-size:13px;color:var(--amber)}
.destrow{display:flex;align-items:center;gap:10px;padding:10px 14px;border-top:1px solid var(--line)}
.destrow .pfx{color:var(--dim);font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:.5px;user-select:none}
.destinput{flex:1;background:var(--panel-2);border:1px solid var(--line);border-radius:7px;outline:none;color:var(--ink);font-family:'JetBrains Mono',monospace;font-size:12px;padding:6px 9px}
.destinput:focus{border-color:var(--amber-line)}
.destinput::placeholder{color:var(--dim)}
.boost select{background:var(--panel-2);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:4px 6px;font-size:12px;outline:none;cursor:pointer}
.boost select:hover{border-color:var(--amber-line)}
.totspeed{font-size:12px;color:var(--amber);font-weight:600}
.prio-ctl{display:flex;flex-direction:column;gap:1px;flex:0 0 auto}
.prio-ctl button{background:transparent;border:none;color:var(--dim);cursor:pointer;font-size:9px;line-height:1;padding:1px 3px;border-radius:3px}
.prio-ctl button:hover{color:var(--amber);background:var(--bg)}
.prio-ctl button:disabled{opacity:.25;cursor:default}
.job-sp{color:var(--amber);font-family:'JetBrains Mono',monospace;font-size:10.5px}
.files-toggle{margin-top:7px;background:transparent;border:none;color:var(--mut);cursor:pointer;font-family:'JetBrains Mono',monospace;font-size:11px;padding:2px 0;display:flex;align-items:center;gap:5px;width:100%;text-align:left}
.files-toggle:hover{color:var(--amber)}
.files-toggle .caret{color:var(--dim);font-size:9px}
.files-summary{color:var(--dim)}
.files-panel{margin-top:5px;max-height:200px;overflow:auto;background:var(--bg);border:1px solid var(--line);border-radius:7px;padding:5px 6px}
.frow{display:flex;align-items:center;gap:7px;padding:2px 4px;font-family:'JetBrains Mono',monospace;font-size:11px;border-radius:4px}
.frow .fi{flex:0 0 12px;text-align:center;font-size:10px}
.frow .fn{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--mut)}
.fr-done .fi{color:var(--grn)}
.fr-done .fn{color:var(--dim)}
.fr-downloading{background:var(--amber-soft)}
.fr-downloading .fi{color:var(--amber)}
.fr-downloading .fn{color:var(--ink)}
.fr-queued .fi{color:var(--dim)}
.fr-error .fi,.fr-stopped .fi{color:var(--red)}
.fr-error .fn,.fr-stopped .fn{color:var(--red)}
.fr-more,.fr-empty{color:var(--dim);justify-content:center;padding:4px}
.tree{padding:8px 6px;max-height:62vh;overflow:auto}
.row{display:flex;align-items:center;gap:8px;padding:5px 8px;border-radius:7px;user-select:none}
.row:hover{background:var(--panel-2)}
.tw{width:16px;height:16px;flex:0 0 16px;display:grid;place-items:center;color:var(--dim);cursor:pointer;font-size:10px;transition:transform .15s}
.tw.open{transform:rotate(90deg);color:var(--amber)}
.tw.leaf{visibility:hidden}
.ck{width:16px;height:16px;flex:0 0 16px;border:1.5px solid var(--line);border-radius:5px;cursor:pointer;display:grid;place-items:center;transition:.12s;background:var(--bg)}
.ck.on{background:var(--amber);border-color:var(--amber)}
.ck.on::after{content:"";width:8px;height:8px;border-radius:2px;background:#1a1206}
.ck.disabled{opacity:.35;pointer-events:none}
.ic{flex:0 0 auto;font-size:13px;width:16px;text-align:center}
.ic.dir{color:var(--amber)}
.ic.file{color:var(--dim)}
.nm{font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row.is-file .nm{color:var(--mut)}
.kids{display:none}
.kids.open{display:block}
.loading-row{padding:6px 8px;color:var(--dim);font-family:'JetBrains Mono',monospace;font-size:12px}
.empty{padding:44px 20px;text-align:center;color:var(--dim)}
.empty .big{font-size:13px;color:var(--mut);margin-bottom:6px}
.foot{display:flex;align-items:center;gap:12px;padding:12px 14px;border-top:1px solid var(--line)}
.sel-count{font-family:'JetBrains Mono',monospace;font-size:12.5px;color:var(--mut)}
.sel-count b{color:var(--amber)}
.spacer{flex:1}
.mon{padding:10px 12px;max-height:66vh;overflow:auto;display:flex;flex-direction:column;gap:10px}
.mon-empty{color:var(--dim);font-size:13px;text-align:center;padding:34px 10px;font-family:'JetBrains Mono',monospace}
.job{background:var(--panel-2);border:1px solid var(--line);border-radius:9px;padding:11px 12px}
.job-top{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.job-nm{font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1 1 auto}
.job-st{font-family:'JetBrains Mono',monospace;font-size:11px;padding:2px 7px;border-radius:5px;flex:0 0 auto}
.st-scanning{color:var(--blu);background:#6ba8f01a}
.st-downloading{color:var(--amber);background:var(--amber-soft)}
.st-done{color:var(--grn);background:#5fd09c1a}
.st-partial{color:var(--amber);background:var(--amber-soft)}
.st-error,.st-stopped{color:var(--red);background:#f06b6b1a}
.track{height:7px;background:var(--bg);border-radius:5px;overflow:hidden}
.fill{height:100%;width:0;background:linear-gradient(90deg,#f0a04b,#f0c074);transition:width .35s ease;border-radius:5px}
.fill.done{background:var(--grn)}
.fill.err{background:var(--red)}
.job-num{margin-top:6px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--dim);display:flex;justify-content:space-between}
.errs{margin-top:6px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--red);max-height:60px;overflow:auto}
.toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%) translateY(20px);background:var(--panel-2);border:1px solid var(--amber-line);color:var(--ink);padding:11px 18px;border-radius:9px;font-size:13px;opacity:0;transition:.25s;pointer-events:none}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
@media(max-width:880px){.cols{grid-template-columns:1fr}.bar{flex-wrap:wrap}}
::-webkit-scrollbar{width:9px;height:9px}
::-webkit-scrollbar-thumb{background:var(--line);border-radius:5px}
::-webkit-scrollbar-thumb:hover{background:#333c4d}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="logo">Snatch<b>Dir</b></div>
    <div class="tag">fetch any open HTTP directory, structure intact</div>
  </header>
  <div class="bar">
    <span class="pfx mono">GET</span>
    <input id="url" class="mono" placeholder="https://example.com/files/" spellcheck="false" autocomplete="off">
    <button class="btn" id="loadBtn" onclick="loadRoot()">Browse</button>
  </div>
  <div class="cols">
    <div class="card">
      <div class="card-h"><h2>Directory</h2>
        <div class="hd-right">
          <input id="search" class="searchbox mono" placeholder="filter…" spellcheck="false" autocomplete="off" oninput="applyFilter()">
          <select id="sortSel" class="sortsel mono" onchange="resort()">
            <option value="name">name ↑</option>
            <option value="name_desc">name ↓</option>
            <option value="size_desc">size ↓</option>
            <option value="size">size ↑</option>
            <option value="date_desc">newest</option>
            <option value="date">oldest</option>
          </select>
          <span class="meta" id="hostMeta"></span>
        </div>
      </div>
      <div class="tree" id="tree">
        <div class="empty"><div class="big">Nothing loaded yet</div><div>Paste a directory URL above and hit Browse.</div></div>
      </div>
      <div class="destrow">
        <span class="pfx mono">SAVE&nbsp;TO</span>
        <input id="dest" class="mono destinput" placeholder="(default: ./downloads) — optional path" spellcheck="false" autocomplete="off">
        <input type="file" id="importFile" accept="application/json,.json" style="display:none" onchange="importSession(event)">
        <button class="btn" onclick="document.getElementById('importFile').click()" title="resume a saved session">Import…</button>
      </div>
      <div class="foot">
        <span class="sel-count"><b id="selN">0</b> folder(s) selected</span>
        <span class="spacer"></span>
        <label class="boost mono" title="files downloaded in parallel">⚡<select id="workers">
          <option value="1">1</option><option value="2">2</option>
          <option value="4" selected>4</option><option value="6">6</option>
          <option value="8">8</option><option value="12">12</option><option value="16">16</option>
        </select></label>
        <label class="boost mono" title="connections per file (segmented)">⛓<select id="conns">
          <option value="1" selected>1</option><option value="2">2</option>
          <option value="4">4</option><option value="6">6</option>
          <option value="8">8</option><option value="16">16</option>
        </select></label>
        <button class="btn" onclick="clearSel()">Clear</button>
        <button class="btn primary" id="dlBtn" onclick="downloadAll()" disabled>Download all</button>
      </div>
    </div>
    <div class="card">
      <div class="card-h"><h2>Transfers</h2>
        <div class="hd-right">
          <span class="totspeed mono" id="totSpeed"></span>
          <button class="btn" id="pauseBtn" onclick="togglePause()" style="display:none;padding:5px 11px">Pause</button>
          <button class="btn" id="exportBtn" onclick="exportSession()" style="display:none;padding:5px 11px">Export</button>
          <button class="btn ghost-red" id="stopBtn" onclick="stopJob()" style="display:none;padding:5px 11px">Stop</button>
        </div>
      </div>
      <div class="mon" id="mon"><div class="mon-empty">idle — no active transfers</div></div>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>
<script>
const $=s=>document.querySelector(s);
const selected=new Map();
let curJob=null, es=null;
let sortMode='name';
let rootEntries=null;
const levels=[];   // {entries, container, depth}
function toast(m){const t=$('#toast');t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2600);}
function fmtSize(n){
  if(n==null)return '';
  const u=['B','K','M','G','T'];let i=0,v=n;
  while(v>=1024&&i<u.length-1){v/=1024;i++;}
  return (i===0?v:v.toFixed(v<10?1:0))+u[i];
}
function fmtDate(t){
  if(t==null)return '';
  const d=new Date(t*1000);
  return d.toISOString().slice(0,16).replace('T',' ');
}
function cmp(mode){
  return (a,b)=>{
    if(a.is_dir!==b.is_dir)return a.is_dir?-1:1;
    switch(mode){
      case 'name_desc':return b.name.toLowerCase().localeCompare(a.name.toLowerCase());
      case 'size':return (a.size||0)-(b.size||0)||a.name.localeCompare(b.name);
      case 'size_desc':return (b.size||0)-(a.size||0)||a.name.localeCompare(b.name);
      case 'date':return (a.mtime||0)-(b.mtime||0)||a.name.localeCompare(b.name);
      case 'date_desc':return (b.mtime||0)-(a.mtime||0)||a.name.localeCompare(b.name);
      default:return a.name.toLowerCase().localeCompare(b.name.toLowerCase());
    }
  };
}
function resort(){
  sortMode=$('#sortSel').value;
  for(const lv of levels){
    lv.entries.sort(cmp(sortMode));
    const order=new Map(lv.entries.map((e,i)=>[e.url,i]));
    const blocks=[...lv.container.children];
    const pairs=[];
    for(let i=0;i<blocks.length;){
      const row=blocks[i];
      const kids=(blocks[i+1]&&blocks[i+1].classList.contains('kids'))?blocks[i+1]:null;
      pairs.push({url:row.dataset.url,nodes:kids?[row,kids]:[row]});
      i+=kids?2:1;
    }
    pairs.sort((a,b)=>(order.get(a.url)??0)-(order.get(b.url)??0));
    for(const p of pairs)for(const n of p.nodes)lv.container.appendChild(n);
  }
}
function highlight(nm,name,q){
  if(!q){nm.textContent=name;return;}
  const i=name.toLowerCase().indexOf(q);
  if(i<0){nm.textContent=name;return;}
  nm.textContent='';
  nm.append(document.createTextNode(name.slice(0,i)));
  const mk=document.createElement('mark');mk.textContent=name.slice(i,i+q.length);
  nm.append(mk,document.createTextNode(name.slice(i+q.length)));
}
let filterToken=0;
async function applyFilter(){
  const q=$('#search').value.trim().toLowerCase();
  const token=++filterToken;
  if(!rootEntries)return;
  if(!q){
    document.querySelectorAll('#tree .row.hide,#tree .kids.hide').forEach(el=>el.classList.remove('hide'));
    document.querySelectorAll('#tree .nm').forEach(nm=>{if(nm._name)nm.textContent=nm._name;});
    return;
  }
  await filterEntries(rootEntries,q,token);
}
async function filterEntries(entries,q,token){
  let anyVisible=false;
  for(const e of entries){
    if(token!==filterToken)return false;
    if(!e._row)continue;
    e._nm._name=e._nm._name||e.name;
    const selfMatch=e.name.toLowerCase().includes(q);
    let childMatch=false;
    if(e.is_dir&&(selfMatch||e._children)){
      if(!e._children&&e._expand)await e._expand();
      if(token!==filterToken)return false;
      if(e._children)childMatch=await filterEntries(e._children,q,token);
    }
    const show=selfMatch||childMatch;
    e._row.classList.toggle('hide',!show);
    if(e._kids){
      e._kids.classList.toggle('hide',!show);
      if(show&&childMatch&&!e._kids.classList.contains('open')&&e._expand)await e._expand();
    }
    highlight(e._nm,e.name,selfMatch?q:'');
    if(show)anyVisible=true;
  }
  return anyVisible;
}
async function loadRoot(){
  let url=$('#url').value.trim();
  if(!url){toast('Enter a URL');return;}
  if(!/^https?:\/\//.test(url)){url='https://'+url;$('#url').value=url;}
  if(!url.endsWith('/'))url+='/';
  const tree=$('#tree');
  tree.innerHTML='<div class="loading-row">scanning '+esc(url)+' …</div>';
  $('#hostMeta').textContent=new URL(url).host;
  selected.clear();updateSel();levels.length=0;rootEntries=null;
  const sb=$('#search');if(sb)sb.value='';
  try{
    const ents=await fetchList(url);
    rootEntries=ents;
    tree.innerHTML='';tree.appendChild(buildLevel(ents,0));
    if(!ents.length)tree.innerHTML='<div class="empty"><div class="big">Empty directory</div></div>';
  }catch(e){tree.innerHTML='<div class="empty"><div class="big">Couldn\'t read that directory</div><div>'+esc(e.message)+'</div></div>';}
}
async function fetchList(url){
  const r=await fetch('/api/list',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url})});
  const d=await r.json();
  if(!r.ok)throw new Error(d.error||'request failed');
  return d.entries;
}
function buildLevel(entries,depth){
  const frag=document.createElement('div');
  entries=entries.slice().sort(cmp(sortMode));
  levels.push({entries,container:frag,depth});
  for(const e of entries){
    const row=document.createElement('div');
    row.className='row'+(e.is_dir?' is-dir':' is-file');
    row.style.paddingLeft=(8+depth*18)+'px';
    row.dataset.url=e.url;
    const tw=document.createElement('span');tw.className='tw'+(e.is_dir?'':' leaf');tw.textContent='▶';
    const ck=document.createElement('span');ck.className='ck'+(e.is_dir?'':' disabled');
    const ic=document.createElement('span');ic.className='ic '+(e.is_dir?'dir':'file');ic.textContent=e.is_dir?'▸':'·';
    const nm=document.createElement('span');nm.className='nm';nm.textContent=e.name;
    const meta=document.createElement('span');meta.className='meta-cols';
    meta.innerHTML='<span class="sz">'+esc(fmtSize(e.size))+'</span><span class="dt">'+esc(fmtDate(e.mtime))+'</span>';
    row.append(tw,ck,ic,nm,meta);frag.appendChild(row);
    e._row=row;e._nm=nm;e._children=null;
    if(e.is_dir){
      const kids=document.createElement('div');kids.className='kids';frag.appendChild(kids);
      e._kids=kids;
      let loaded=false;
      const doLoad=async()=>{
        if(loaded)return;
        loaded=true;
        kids.innerHTML='<div class="loading-row" style="padding-left:'+(26+depth*18)+'px">loading…</div>';
        try{const sub=await fetchList(e.url);e._children=sub;kids.innerHTML='';kids.appendChild(buildLevel(sub,depth+1));}
        catch(err){kids.innerHTML='<div class="loading-row" style="color:var(--red);padding-left:'+(26+depth*18)+'px">'+esc(err.message)+'</div>';}
      };
      e._expand=async()=>{
        if(!kids.classList.contains('open')){kids.classList.add('open');tw.classList.add('open');ic.textContent='▾';}
        await doLoad();
      };
      const toggle=async()=>{
        const open=kids.classList.toggle('open');
        tw.classList.toggle('open',open);ic.textContent=open?'▾':'▸';
        if(open)await doLoad();
      };
      tw.onclick=toggle;nm.onclick=toggle;nm.style.cursor='pointer';
      ck.onclick=ev=>{ev.stopPropagation();toggleSel(e,ck);};
    }
  }
  return frag;
}
function toggleSel(e,ck){
  if(selected.has(e.url)){selected.delete(e.url);ck.classList.remove('on');}
  else{selected.set(e.url,{name:e.name,url:e.url,el:ck});ck.classList.add('on');}
  updateSel();
}
function clearSel(){selected.forEach(v=>v.el.classList.remove('on'));selected.clear();updateSel();}
function updateSel(){$('#selN').textContent=selected.size;$('#dlBtn').disabled=selected.size===0||curJob!==null;}
function pruneNested(list){
  const urls=new Set(list.map(x=>x.url));
  return list.filter(x=>{
    let u=x.url.replace(/\/$/,'');const parts=u.split('/');
    for(let i=parts.length-1;i>3;i--){const anc=parts.slice(0,i).join('/')+'/';if(urls.has(anc)&&anc!==x.url)return false;}
    return true;
  });
}
function fmtSpeed(bps){
  if(!bps||bps<1)return '—';
  const u=['B/s','KB/s','MB/s','GB/s'];let i=0,v=bps;
  while(v>=1024&&i<u.length-1){v/=1024;i++;}
  return (v<10?v.toFixed(1):Math.round(v))+' '+u[i];
}
let jobOrder=[];
let paused=false;
function showJobControls(){
  $('#dlBtn').disabled=true;
  $('#stopBtn').style.display='';
  $('#pauseBtn').style.display='';
  $('#exportBtn').style.display='';
  paused=false;$('#pauseBtn').textContent='Pause';
}
function hideJobControls(){
  $('#stopBtn').style.display='none';
  $('#pauseBtn').style.display='none';
  $('#exportBtn').style.display='none';
  $('#totSpeed').textContent='';
}
async function downloadAll(){
  let folders=pruneNested([...selected.values()].map(v=>({name:v.name,url:v.url})));
  if(!folders.length){toast('Select at least one folder');return;}
  folders=folders.map((f,i)=>({...f,id:'f'+i}));
  const workers=parseInt($('#workers').value,10)||4;
  const conns=parseInt($('#conns').value,10)||1;
  const dest=$('#dest').value.trim();
  const r=await fetch('/api/download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({folders,workers,conns,dest})});
  const d=await r.json();
  if(!r.ok){toast(d.error||'failed');return;}
  curJob=d.job_id;jobOrder=folders.map(f=>f.id);showJobControls();
  renderMon(folders);listen(d.job_id);
  toast('Saving to '+d.dest);
}
async function togglePause(){
  if(!curJob)return;
  paused=!paused;
  $('#pauseBtn').textContent=paused?'Resume':'Pause';
  await fetch('/api/pause/'+curJob,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({paused})});
  toast(paused?'Paused':'Resumed');
}
function exportSession(){
  if(!curJob){toast('No active session');return;}
  const a=document.createElement('a');
  a.href='/api/session/'+curJob;a.download='';
  document.body.appendChild(a);a.click();a.remove();
  toast('Session exported');
}
async function importSession(ev){
  const file=ev.target.files[0];ev.target.value='';
  if(!file)return;
  let state;
  try{state=JSON.parse(await file.text());}
  catch(e){toast('Invalid JSON file');return;}
  if(!state.folders||!state.folders.length){toast('Not a SnatchDir session');return;}
  const workers=parseInt($('#workers').value,10)||state.workers||4;
  const conns=parseInt($('#conns').value,10)||state.conns||1;
  const dest=$('#dest').value.trim()||state.dest||'';
  const r=await fetch('/api/resume',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({state,workers,conns,dest})});
  const d=await r.json();
  if(!r.ok){toast(d.error||'resume failed');return;}
  curJob=d.job_id;jobOrder=state.folders.map(f=>f.id);showJobControls();
  renderMon(state.folders);listen(d.job_id);
  toast('Resumed — skipping completed files');
}
function renderMon(folders){
  const mon=$('#mon');mon.innerHTML='';
  for(const f of folders){
    const j=document.createElement('div');j.className='job';j.id='job-'+f.id;j.dataset.fid=f.id;
    j.innerHTML=`<div class="job-top">
        <div class="prio-ctl">
          <button title="raise priority" onclick="movePrio('${f.id}',-1)">▲</button>
          <button title="lower priority" onclick="movePrio('${f.id}',1)">▼</button>
        </div>
        <span class="job-nm">${esc(f.name)}</span>
        <span class="job-sp"></span>
        <span class="job-st st-scanning">scanning</span>
      </div>
      <div class="track"><div class="fill"></div></div>
      <div class="job-num"><span class="pct">0%</span><span class="cnt">—</span></div>
      <button class="files-toggle" onclick="toggleFiles('${f.id}')"><span class="caret">▸</span> files <span class="files-summary"></span></button>
      <div class="files-panel" style="display:none"><div class="files-list"></div></div>
      <div class="errs" style="display:none"></div>`;
    mon.appendChild(j);
  }
  refreshPrioBtns();
}
function refreshPrioBtns(){
  const cards=[...document.querySelectorAll('#mon .job')];
  cards.forEach((c,i)=>{
    const btns=c.querySelectorAll('.prio-ctl button');
    btns[0].disabled=(i===0);btns[1].disabled=(i===cards.length-1);
  });
}
async function movePrio(fid,dir){
  const i=jobOrder.indexOf(fid);if(i<0)return;
  const j=i+dir;if(j<0||j>=jobOrder.length)return;
  [jobOrder[i],jobOrder[j]]=[jobOrder[j],jobOrder[i]];
  const mon=$('#mon');
  const cards=Object.fromEntries([...mon.children].map(c=>[c.dataset.fid,c]));
  for(const id of jobOrder)mon.appendChild(cards[id]);
  refreshPrioBtns();
  if(curJob)fetch('/api/priority/'+curJob,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({order:jobOrder})});
}
const filesOpen=new Set();
function toggleFiles(fid){
  const j=$('#job-'+fid);if(!j)return;
  const panel=j.querySelector('.files-panel');
  const caret=j.querySelector('.caret');
  const open=panel.style.display==='none';
  panel.style.display=open?'':'none';
  caret.textContent=open?'▾':'▸';
  if(open){filesOpen.add(fid);if(lastItems[fid])paintFiles(fid,lastItems[fid]);}
  else filesOpen.delete(fid);
}
const ST_ICON={done:'✔',downloading:'↓',queued:'•',error:'✕',stopped:'■'};
function paintFiles(fid,it){
  const j=$('#job-'+fid);if(!j)return;
  const files=it.files||{};
  const names=Object.keys(files);
  let dn=0,dl=0,q=0,er=0;
  for(const k of names){const s=files[k];if(s==='done')dn++;else if(s==='downloading')dl++;else if(s==='error'||s==='stopped')er++;else q++;}
  const sum=j.querySelector('.files-summary');
  sum.textContent=names.length?`(${dn} done · ${dl} active · ${q} queued${er?` · ${er} failed`:''})`:'';
  if(!filesOpen.has(fid))return;
  const list=j.querySelector('.files-list');
  // sort: active first, then queued, then done, then failed; cap to 400 rows for huge folders
  const rank={downloading:0,queued:1,done:2,error:3,stopped:3};
  const sorted=names.sort((a,b)=>(rank[files[a]]??9)-(rank[files[b]]??9)||a.localeCompare(b));
  const cap=400;
  let html=sorted.slice(0,cap).map(n=>{
    const s=files[n];
    return `<div class="frow fr-${s}"><span class="fi">${ST_ICON[s]||'•'}</span><span class="fn">${esc(n)}</span></div>`;
  }).join('');
  if(sorted.length>cap)html+=`<div class="frow fr-more">… ${sorted.length-cap} more</div>`;
  list.innerHTML=html||'<div class="frow fr-empty">no files yet</div>';
}
function listen(jobId){
  if(es)es.close();
  es=new EventSource('/api/progress/'+jobId);
  es.onmessage=ev=>{
    const d=JSON.parse(ev.data);
    if(d.error){es.close();return;}
    for(const id in d.items)paint(id,d.items[id]);
    $('#totSpeed').textContent=d.finished?'':(d.paused?'paused':fmtSpeed(d.speed));
    if(d.finished){es.close();es=null;curJob=null;hideJobControls();updateSel();toast('All transfers complete');}
  };
  es.onerror=()=>{if(es){es.close();es=null;}};
}
const lastItems={};
function paint(id,it){
  lastItems[id]=it;
  const j=$('#job-'+id);if(!j)return;
  const pct=it.total?Math.round(it.done/it.total*100):0;
  const fill=j.querySelector('.fill');fill.style.width=pct+'%';
  j.querySelector('.pct').textContent=pct+'%';
  j.querySelector('.cnt').textContent=it.done+' / '+it.total+' files';
  const sp=j.querySelector('.job-sp');
  sp.textContent=(it.status==='downloading'&&it.speed)?fmtSpeed(it.speed):'';
  const st=j.querySelector('.job-st');let cls=it.status,label=it.status;
  if(it.status==='done')fill.classList.add('done');
  else if(it.status==='error'||it.status==='stopped')fill.classList.add('err');
  else if(it.status==='queued'){cls='scanning';label='queued';}
  else if(it.status!=='scanning'&&it.status!=='partial'){cls='downloading';label='downloading';}
  st.className='job-st st-'+cls;st.textContent=label;
  if(it.errors&&it.errors.length){const e=j.querySelector('.errs');e.style.display='';e.innerHTML=it.errors.slice(-5).map(x=>esc(x)).join('<br>');}
  paintFiles(id,it);
}
async function stopJob(){if(!curJob)return;await fetch('/api/stop/'+curJob,{method:'POST'});toast('Stopping…');}
function esc(s){return (s+'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
$('#url').addEventListener('keydown',e=>{if(e.key==='Enter')loadRoot();});
</script>
</body>
</html>"""


if __name__ == "__main__":
    app.run(debug=True, threaded=True, port=5000)
