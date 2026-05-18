from flask import Flask, request, render_template_string, send_from_directory, send_file, jsonify
import os, zipfile, io, datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "x7k2p9q"

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

BASE_DIR = os.path.realpath(os.getcwd())


def safe_path(relpath):
    """Resolve relative path, ensure it stays within BASE_DIR."""
    clean = relpath.lstrip('/').lstrip('\\') if relpath else ''
    resolved = os.path.realpath(os.path.join(BASE_DIR, clean))
    if not resolved.startswith(BASE_DIR):
        return None
    return resolved


HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DROPZONE</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=Syne:wght@700;800&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
:root{
  --bg:#070709;--s1:#0d0d10;--s2:#13131a;--s3:#1a1a24;
  --border:#1f1f2e;--border2:#2a2a3a;
  --ac:#00e5ff;--ac2:#00ff9d;--ac3:#ff6b35;
  --danger:#ff3d5a;--warn:#ffb347;
  --text:#cccce0;--muted:#4a4a6a;--muted2:#333348;
  --mono:'JetBrains Mono',monospace;--display:'Syne',sans-serif;
}
body{background:var(--bg);color:var(--text);font-family:var(--mono);min-height:100vh;}
body::after{
  content:'';position:fixed;inset:0;
  background:repeating-linear-gradient(0deg,transparent,transparent 3px,rgba(0,0,0,0.05) 3px,rgba(0,0,0,0.05) 4px);
  pointer-events:none;z-index:9999;
}
.shell{display:flex;flex-direction:column;height:100vh;}

/* ── Topbar ── */
.topbar{
  display:flex;align-items:center;
  background:var(--s1);border-bottom:1px solid var(--border);
  padding:0 1.5rem;height:52px;flex-shrink:0;gap:0;
}
.logo{
  font-family:var(--display);font-size:1.1rem;font-weight:800;
  letter-spacing:0.25em;color:var(--ac);text-transform:uppercase;
  margin-right:2.5rem;white-space:nowrap;
}
.logo em{color:var(--muted);font-style:normal;}
.tabs{display:flex;height:100%;align-items:stretch;}
.tab{
  display:flex;align-items:center;gap:0.45rem;
  padding:0 1.3rem;font-size:0.68rem;letter-spacing:0.14em;
  text-transform:uppercase;color:var(--muted);cursor:pointer;
  border-bottom:2px solid transparent;transition:all 0.2s;
  white-space:nowrap;user-select:none;
}
.tab:hover{color:var(--text);}
.tab.active{color:var(--ac);border-bottom-color:var(--ac);}
.topbar-right{margin-left:auto;display:flex;gap:0.6rem;align-items:center;}
.btn-sm{
  background:transparent;border:1px solid var(--border2);color:var(--muted);
  padding:0.35rem 0.85rem;font-family:var(--mono);font-size:0.65rem;
  letter-spacing:0.12em;cursor:pointer;text-decoration:none;
  text-transform:uppercase;transition:all 0.2s;white-space:nowrap;display:inline-block;
}
.btn-sm:hover{border-color:var(--ac2);color:var(--ac2);}
.btn-sm.primary{border-color:var(--ac);color:var(--ac);}
.btn-sm.primary:hover{background:var(--ac);color:#000;}

/* ── Panes ── */
.pane{display:none;flex:1;overflow:hidden;}
.pane.active{display:flex;flex-direction:column;}

/* ══ UPLOAD PANE ══ */
.upload-pane{padding:1.5rem;gap:1.2rem;overflow-y:auto;}
#dropzone{
  border:1px dashed var(--muted2);background:var(--s1);border-radius:6px;
  padding:2.5rem 2rem;text-align:center;cursor:pointer;
  transition:all 0.25s;position:relative;overflow:hidden;flex-shrink:0;
}
#dropzone::before{
  content:'';position:absolute;inset:0;
  background:radial-gradient(ellipse at 50% 60%,rgba(0,229,255,0.07) 0%,transparent 65%);
  opacity:0;transition:opacity 0.3s;
}
#dropzone.over{border-color:var(--ac);background:#080c10;}
#dropzone.over::before{opacity:1;}
.dz-icon{font-size:2rem;color:var(--muted2);margin-bottom:0.6rem;display:block;transition:all 0.25s;}
#dropzone.over .dz-icon{color:var(--ac);transform:translateY(-4px);}
.dz-text{font-size:0.75rem;letter-spacing:0.08em;color:var(--muted);text-transform:uppercase;}
.dz-text strong{color:var(--ac);}
.dz-sub{font-size:0.6rem;color:var(--muted2);margin-top:0.3rem;letter-spacing:0.05em;}
#file-input{display:none;}
#prog-wrap{display:none;flex-shrink:0;}
.prog-meta{
  display:flex;justify-content:space-between;font-size:0.65rem;
  letter-spacing:0.08em;color:var(--muted);text-transform:uppercase;margin-bottom:0.4rem;
}
.prog-track{background:var(--s2);height:3px;border-radius:2px;overflow:hidden;}
.prog-fill{height:100%;width:0%;background:linear-gradient(90deg,var(--ac),var(--ac2));box-shadow:0 0 8px var(--ac);transition:width 0.1s;}
#staging{display:none;flex-shrink:0;}
.staging-hdr{font-size:0.65rem;letter-spacing:0.1em;color:var(--muted);text-transform:uppercase;margin-bottom:0.5rem;}
#staged-list{display:flex;flex-wrap:wrap;gap:0.5rem;margin-bottom:0.75rem;}
.s-item{
  background:var(--s2);border:1px solid var(--border);border-radius:3px;
  padding:0.35rem 0.5rem;display:flex;align-items:center;gap:0.4rem;
  font-size:0.65rem;max-width:180px;
}
.s-thumb{width:28px;height:28px;object-fit:cover;border-radius:2px;flex-shrink:0;}
.s-icon{
  width:28px;height:28px;display:flex;align-items:center;justify-content:center;
  background:var(--s3);border-radius:2px;font-size:0.9rem;flex-shrink:0;
}
.s-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.btn-upload{
  background:var(--ac);color:#000;border:none;padding:0.5rem 1.3rem;
  font-family:var(--mono);font-size:0.7rem;font-weight:700;
  letter-spacing:0.15em;cursor:pointer;text-transform:uppercase;transition:opacity 0.2s;
}
.btn-upload:hover{opacity:0.82;}
.up-sec-hdr{
  font-size:0.62rem;letter-spacing:0.18em;color:var(--muted);
  text-transform:uppercase;display:flex;align-items:center;gap:0.6rem;flex-shrink:0;
}
.up-sec-hdr::after{content:'';flex:1;height:1px;background:var(--border);}
#file-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:0.75rem;}
.f-card{
  background:var(--s1);border:1px solid var(--border);border-radius:4px;
  overflow:hidden;transition:border-color 0.2s,transform 0.2s;
}
.f-card:hover{border-color:var(--ac);transform:translateY(-2px);}
.f-prev{width:100%;height:110px;background:var(--s2);display:flex;align-items:center;justify-content:center;overflow:hidden;}
.f-prev img{width:100%;height:100%;object-fit:cover;}
.f-prev .pdf-wrap{width:100%;height:100%;overflow:hidden;}
.f-prev .pdf-wrap iframe{width:200%;height:200%;transform:scale(0.5);transform-origin:0 0;border:none;pointer-events:none;}
.f-prev .bigico{font-size:2.4rem;opacity:0.3;}
.f-info{padding:0.5rem 0.6rem;}
.f-name{font-size:0.65rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--text);margin-bottom:0.25rem;}
.f-meta{font-size:0.58rem;color:var(--muted);display:flex;justify-content:space-between;align-items:center;}
.f-acts{display:flex;gap:0.3rem;}
.fa-dl,.fa-rm{background:transparent;border:none;cursor:pointer;font-size:0.72rem;padding:1px 3px;transition:opacity 0.2s;}
.fa-dl{color:var(--ac);}.fa-rm{color:var(--danger);}
.fa-dl:hover,.fa-rm:hover{opacity:0.6;}
.empty-msg{grid-column:1/-1;text-align:center;padding:2.5rem;color:var(--muted2);font-size:0.7rem;letter-spacing:0.08em;}

/* ══ BROWSE PANE ══ */
.browse-pane{flex-direction:column;}
.fs-toolbar{
  display:flex;align-items:center;gap:0.7rem;
  padding:0.65rem 1.5rem;background:var(--s1);
  border-bottom:1px solid var(--border);flex-shrink:0;flex-wrap:wrap;
}
.fs-nav-btn{
  background:var(--s2);border:1px solid var(--border);
  color:var(--muted);padding:0.3rem 0.65rem;
  font-family:var(--mono);font-size:0.68rem;cursor:pointer;
  border-radius:3px;transition:all 0.15s;
}
.fs-nav-btn:hover:not(:disabled){border-color:var(--ac);color:var(--ac);}
.fs-nav-btn:disabled{opacity:0.3;cursor:not-allowed;}
.breadcrumb{
  display:flex;align-items:center;gap:0;font-size:0.68rem;
  flex:1;min-width:0;overflow:hidden;
}
.bc-seg{
  color:var(--muted);cursor:pointer;padding:0.2rem 0.3rem;
  border-radius:2px;transition:color 0.15s;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;max-width:180px;
}
.bc-seg:hover{color:var(--ac);}
.bc-seg.last{color:var(--text);cursor:default;pointer-events:none;}
.bc-sep{color:var(--muted2);padding:0 0.05rem;user-select:none;}
.fs-search-wrap{position:relative;}
.fs-search{
  background:var(--s2);border:1px solid var(--border);
  color:var(--text);padding:0.3rem 0.6rem 0.3rem 1.8rem;
  font-family:var(--mono);font-size:0.68rem;
  border-radius:3px;width:190px;transition:border-color 0.2s;
}
.fs-search::placeholder{color:var(--muted2);}
.fs-search:focus{outline:none;border-color:var(--ac);}
.fs-search-icon{position:absolute;left:0.55rem;top:50%;transform:translateY(-50%);color:var(--muted2);font-size:0.75rem;pointer-events:none;}
.fs-sort-btn{
  background:var(--s2);border:1px solid var(--border);
  color:var(--muted);padding:0.3rem 0.55rem;font-family:var(--mono);
  font-size:0.63rem;letter-spacing:0.05em;cursor:pointer;border-radius:3px;
  transition:all 0.15s;text-transform:uppercase;
}
.fs-sort-btn.active{border-color:var(--ac2);color:var(--ac2);}
.hidden-toggle{
  display:flex;align-items:center;gap:0.35rem;font-size:0.62rem;
  color:var(--muted);cursor:pointer;user-select:none;white-space:nowrap;
}
.hidden-toggle input{accent-color:var(--ac);}
.fs-statbar{
  display:flex;align-items:center;gap:1.5rem;padding:0.35rem 1.5rem;
  background:var(--s2);border-bottom:1px solid var(--border);
  font-size:0.6rem;letter-spacing:0.07em;color:var(--muted);flex-shrink:0;
}
.fs-statbar span{display:flex;align-items:center;gap:0.35rem;}
.sdot{width:6px;height:6px;border-radius:50%;background:var(--muted2);}
.sdot.d{background:var(--warn);}.sdot.f{background:var(--ac);}
.fs-body{flex:1;overflow-y:auto;}
.fs-table{width:100%;border-collapse:collapse;}
.fs-table thead th{
  position:sticky;top:0;background:var(--s2);padding:0.45rem 1rem;
  font-size:0.58rem;letter-spacing:0.12em;text-transform:uppercase;
  color:var(--muted);text-align:left;border-bottom:1px solid var(--border);
  cursor:pointer;user-select:none;white-space:nowrap;transition:color 0.15s;
}
.fs-table thead th:hover{color:var(--text);}
.fs-table thead th.asc::after{content:' ↑';}
.fs-table thead th.desc::after{content:' ↓';}
.fs-table tbody tr{
  border-bottom:1px solid var(--border);
  transition:background 0.12s;
  animation:rowIn 0.18s ease both;
}
.fs-table tbody tr:hover{background:var(--s2);}
@keyframes rowIn{from{opacity:0;transform:translateX(-5px);}to{opacity:1;transform:none;}}
.fs-table td{padding:0.5rem 1rem;font-size:0.7rem;vertical-align:middle;}
.td-icon{width:38px;padding-right:0;}
.fs-ico{
  width:28px;height:28px;display:flex;align-items:center;
  justify-content:center;border-radius:4px;font-size:1rem;
  background:var(--s3);flex-shrink:0;
}
.td-name{min-width:200px;}
.fs-name{display:flex;align-items:center;gap:0.55rem;}
.name-text{color:var(--text);font-size:0.72rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:320px;}
.fs-name.is-dir .name-text{color:var(--warn);cursor:pointer;}
.fs-name.is-dir .name-text:hover{text-decoration:underline;}
.ext-badge{font-size:0.52rem;letter-spacing:0.07em;text-transform:uppercase;padding:1px 5px;border-radius:2px;flex-shrink:0;}
.ext-img{background:rgba(0,229,255,0.12);color:var(--ac);}
.ext-code{background:rgba(255,179,71,0.12);color:var(--warn);}
.ext-doc{background:rgba(100,150,255,0.15);color:#6496ff;}
.ext-arc{background:rgba(255,107,53,0.12);color:var(--ac3);}
.ext-exec{background:rgba(255,61,90,0.12);color:var(--danger);}
.ext-media{background:rgba(180,100,255,0.15);color:#b464ff;}
.ext-data{background:rgba(0,255,157,0.1);color:var(--ac2);}
.ext-other{background:var(--s3);color:var(--muted);}
.td-size,.td-modified,.td-perms{color:var(--muted);font-size:0.63rem;white-space:nowrap;}
.td-acts{width:80px;text-align:right;}
.row-act{
  background:transparent;border:1px solid transparent;
  color:var(--muted);padding:0.22rem 0.5rem;
  font-size:0.63rem;font-family:var(--mono);cursor:pointer;
  border-radius:2px;transition:all 0.15s;text-decoration:none;display:inline-block;
}
.row-act:hover{border-color:var(--ac2);color:var(--ac2);}
.row-act.dir:hover{border-color:var(--warn);color:var(--warn);}
.fs-empty{text-align:center;padding:4rem;color:var(--muted2);font-size:0.7rem;letter-spacing:0.1em;}

/* ── Scrollbar ── */
::-webkit-scrollbar{width:4px;height:4px;}
::-webkit-scrollbar-track{background:var(--bg);}
::-webkit-scrollbar-thumb{background:var(--muted2);border-radius:2px;}
::-webkit-scrollbar-thumb:hover{background:var(--muted);}

/* ── Toast ── */
#toast{
  position:fixed;bottom:1.5rem;right:1.5rem;
  background:var(--s2);border:1px solid var(--ac2);color:var(--ac2);
  padding:0.6rem 1rem;font-size:0.7rem;letter-spacing:0.05em;
  border-radius:3px;opacity:0;transform:translateY(8px);
  transition:all 0.25s;z-index:10000;pointer-events:none;
}
#toast.show{opacity:1;transform:translateY(0);}
#toast.err{border-color:var(--danger);color:var(--danger);}
</style>
</head>
<body>
<div class="shell">

<!-- Topbar -->
<div class="topbar">
  <div class="logo">DROP<em>//</em>ZONE</div>
  <div class="tabs">
    <div class="tab active" data-pane="upload" onclick="switchTab('upload')">
      <span>⬆</span> Upload
    </div>
    <div class="tab" data-pane="browse" onclick="switchTab('browse')">
      <span>📂</span> File Browser
    </div>
  </div>
  <div class="topbar-right">
    <a href="/download-all" class="btn-sm primary">⬇ Download All (.zip)</a>
  </div>
</div>

<!-- ══ UPLOAD PANE ══ -->
<div class="pane upload-pane active" id="pane-upload">
  <div id="dropzone" onclick="document.getElementById('file-input').click()">
    <input type="file" id="file-input" multiple>
    <span class="dz-icon">⬡</span>
    <div class="dz-text">Drop files here or <strong>browse</strong></div>
    <div class="dz-sub">Multiple files · Images · PDFs · Any format</div>
  </div>

  <div id="prog-wrap">
    <div class="prog-meta">
      <span id="prog-txt">Uploading…</span>
      <span id="prog-pct">0%</span>
    </div>
    <div class="prog-track"><div class="prog-fill" id="prog-fill"></div></div>
  </div>

  <div id="staging">
    <div class="staging-hdr">Queued — <span id="q-count">0</span> file(s)</div>
    <div id="staged-list"></div>
    <button class="btn-upload" onclick="doUpload()">⬆ Upload Now</button>
  </div>

  <div class="up-sec-hdr">Uploaded Files</div>
  <div id="file-grid"></div>
</div>

<!-- ══ BROWSE PANE ══ -->
<div class="pane browse-pane" id="pane-browse">
  <div class="fs-toolbar">
    <button class="fs-nav-btn" id="btn-up" onclick="fsGoUp()" disabled>↑ Up</button>
    <button class="fs-nav-btn" onclick="fsHome()">⌂ Root</button>
    <div class="breadcrumb" id="breadcrumb"></div>
    <div class="fs-search-wrap">
      <span class="fs-search-icon">⌕</span>
      <input class="fs-search" id="fs-search" type="text" placeholder="Filter files…" oninput="renderFsTable()">
    </div>
    <button class="fs-sort-btn active" id="sort-name" onclick="fsSort('name')">Name</button>
    <button class="fs-sort-btn" id="sort-size" onclick="fsSort('size')">Size</button>
    <button class="fs-sort-btn" id="sort-date" onclick="fsSort('date')">Date</button>
    <label class="hidden-toggle">
      <input type="checkbox" id="show-hidden" onchange="fsLoad()"> Hidden
    </label>
  </div>
  <div class="fs-statbar" id="fs-statbar">
    <span><span class="sdot"></span>Loading…</span>
  </div>
  <div class="fs-body">
    <table class="fs-table">
      <thead>
        <tr>
          <th class="td-icon"></th>
          <th class="td-name">Name</th>
          <th class="td-size">Size</th>
          <th class="td-modified">Modified</th>
          <th class="td-perms">Permissions</th>
          <th class="td-acts"></th>
        </tr>
      </thead>
      <tbody id="fs-tbody"></tbody>
    </table>
  </div>
</div>

</div><!-- /shell -->
<div id="toast"></div>

<script>
// ── Tab switching ─────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.pane === name));
  document.querySelectorAll('.pane').forEach(p => p.classList.toggle('active', p.id === 'pane-' + name));
  if (name === 'browse' && !fsBrowsed) { fsBrowsed = true; fsHome(); }
}
let fsBrowsed = false;

// ── Upload ────────────────────────────────────────
const dz = document.getElementById('dropzone');
const fi = document.getElementById('file-input');
let staged = [];

dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('over'); });
dz.addEventListener('dragleave', () => dz.classList.remove('over'));
dz.addEventListener('drop', e => { e.preventDefault(); dz.classList.remove('over'); stageFiles([...e.dataTransfer.files]); });
fi.addEventListener('change', () => { stageFiles([...fi.files]); fi.value = ''; });

function stageFiles(files) {
  staged = [...staged, ...files];
  renderStaging();
}

function renderStaging() {
  const wrap = document.getElementById('staging');
  const list = document.getElementById('staged-list');
  document.getElementById('q-count').textContent = staged.length;
  if (!staged.length) { wrap.style.display = 'none'; return; }
  wrap.style.display = 'block';
  list.innerHTML = '';
  staged.forEach(f => {
    const item = document.createElement('div');
    item.className = 's-item';
    if (f.type.startsWith('image/')) {
      const img = document.createElement('img');
      img.className = 's-thumb';
      const r = new FileReader();
      r.onload = e => img.src = e.target.result;
      r.readAsDataURL(f);
      item.appendChild(img);
    } else {
      const ic = document.createElement('div');
      ic.className = 's-icon';
      ic.textContent = extIcon(f.name.split('.').pop().toLowerCase());
      item.appendChild(ic);
    }
    const n = document.createElement('div');
    n.className = 's-name';
    n.textContent = f.name;
    item.appendChild(n);
    list.appendChild(item);
  });
}

function doUpload() {
  if (!staged.length) return;
  const fd = new FormData();
  staged.forEach(f => fd.append('files', f));
  const wrap = document.getElementById('prog-wrap');
  const fill = document.getElementById('prog-fill');
  const pct  = document.getElementById('prog-pct');
  const txt  = document.getElementById('prog-txt');
  document.getElementById('staging').style.display = 'none';
  wrap.style.display = 'block';
  const xhr = new XMLHttpRequest();
  xhr.upload.onprogress = e => {
    if (e.lengthComputable) {
      const p = Math.round(e.loaded / e.total * 100);
      fill.style.width = p + '%';
      pct.textContent = p + '%';
      txt.textContent = `Uploading ${staged.length} file(s)…`;
    }
  };
  xhr.onload = () => {
    fill.style.width = '100%';
    setTimeout(() => { wrap.style.display = 'none'; fill.style.width = '0%'; }, 700);
    staged = [];
    toast('✓ Upload complete');
    loadUploads();
  };
  xhr.onerror = () => toast('✗ Upload failed', true);
  xhr.open('POST', '/upload');
  xhr.send(fd);
}

function loadUploads() {
  fetch('/files').then(r => r.json()).then(renderGrid);
}

function renderGrid(files) {
  const grid = document.getElementById('file-grid');
  grid.innerHTML = '';
  if (!files.length) { grid.innerHTML = '<div class="empty-msg">No uploads yet.</div>'; return; }
  files.forEach(f => {
    const ext = f.name.split('.').pop().toLowerCase();
    const isImg = ['jpg','jpeg','png','gif','webp','bmp','svg'].includes(ext);
    const isPdf = ext === 'pdf';
    const url   = '/uploads/' + encodeURIComponent(f.name);
    let preview;
    if (isImg) preview = `<img src="${url}" alt="" loading="lazy">`;
    else if (isPdf) preview = `<div class="pdf-wrap"><iframe src="${url}#toolbar=0&navpanes=0" scrolling="no"></iframe></div>`;
    else preview = `<div class="bigico">${extIcon(ext)}</div>`;
    const card = document.createElement('div');
    card.className = 'f-card';
    card.innerHTML = `
      <div class="f-prev">${preview}</div>
      <div class="f-info">
        <div class="f-name" title="${f.name}">${f.name}</div>
        <div class="f-meta">
          <span>${fmtSize(f.size)}</span>
          <div class="f-acts">
            <a class="fa-dl" href="${url}" download>⬇</a>
            <button class="fa-rm" onclick="delUpload('${f.name}')">✕</button>
          </div>
        </div>
      </div>`;
    grid.appendChild(card);
  });
}

function delUpload(name) {
  fetch('/delete/' + encodeURIComponent(name), { method: 'DELETE' })
    .then(() => { toast('✓ Deleted ' + name); loadUploads(); });
}

// ── File Browser ──────────────────────────────────
let fsPath    = '';
let fsDirData = [];
let fsSortKey = 'name';
let fsSortAsc = true;

function fsHome()  { fsNavigate(''); }
function fsGoUp()  {
  const parts = fsPath.split('/').filter(Boolean);
  parts.pop();
  fsNavigate(parts.join('/'));
}
function fsNavigate(p) { fsPath = p; fsLoad(); }

function fsLoad() {
  const hidden = document.getElementById('show-hidden').checked;
  fetch(`/fs?path=${encodeURIComponent(fsPath)}&hidden=${hidden}`)
    .then(r => r.json())
    .then(data => {
      if (data.error) { toast(data.error, true); return; }
      fsDirData = data.entries;
      renderBreadcrumb(data.path_parts);
      renderStatBar(data.entries);
      document.getElementById('btn-up').disabled = !fsPath;
      renderFsTable();
    })
    .catch(() => toast('Failed to load directory', true));
}

function renderBreadcrumb(parts) {
  const bc = document.getElementById('breadcrumb');
  bc.innerHTML = '';
  const root = document.createElement('span');
  root.className = 'bc-seg' + (!parts.length ? ' last' : '');
  root.textContent = '~ root';
  root.onclick = () => { if (parts.length) fsHome(); };
  bc.appendChild(root);
  let cumPath = '';
  parts.forEach((seg, i) => {
    const sep = document.createElement('span');
    sep.className = 'bc-sep'; sep.textContent = ' / ';
    bc.appendChild(sep);
    cumPath += (cumPath ? '/' : '') + seg;
    const captured = cumPath;
    const span = document.createElement('span');
    span.className = 'bc-seg' + (i === parts.length - 1 ? ' last' : '');
    span.textContent = seg;
    span.onclick = () => { if (i < parts.length - 1) fsNavigate(captured); };
    bc.appendChild(span);
  });
}

function renderStatBar(entries) {
  const dirs  = entries.filter(e => e.is_dir).length;
  const files = entries.filter(e => !e.is_dir).length;
  const total = entries.filter(e => !e.is_dir).reduce((s, e) => s + e.size, 0);
  document.getElementById('fs-statbar').innerHTML =
    `<span><span class="sdot d"></span>${dirs} folder${dirs !== 1 ? 's' : ''}</span>
     <span><span class="sdot f"></span>${files} file${files !== 1 ? 's' : ''}</span>
     <span>Total size: ${fmtSize(total)}</span>`;
}

function fsSort(key) {
  fsSortAsc = fsSortKey === key ? !fsSortAsc : true;
  fsSortKey = key;
  ['name','size','date'].forEach(k => {
    document.getElementById('sort-' + k).classList.toggle('active', k === fsSortKey);
  });
  renderFsTable();
}

function renderFsTable() {
  const q     = document.getElementById('fs-search').value.toLowerCase();
  const tbody = document.getElementById('fs-tbody');
  tbody.innerHTML = '';

  let entries = fsDirData.filter(e => !q || e.name.toLowerCase().includes(q));

  entries.sort((a, b) => {
    if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1;
    let av, bv;
    if (fsSortKey === 'size')      { av = a.size; bv = b.size; }
    else if (fsSortKey === 'date') { av = a.modified; bv = b.modified; }
    else                           { av = a.name.toLowerCase(); bv = b.name.toLowerCase(); }
    if (av < bv) return fsSortAsc ? -1 : 1;
    if (av > bv) return fsSortAsc ?  1 : -1;
    return 0;
  });

  if (!entries.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="fs-empty">Nothing here.</td></tr>';
    return;
  }

  entries.forEach((e, i) => {
    const ext   = e.is_dir ? '' : e.name.split('.').pop().toLowerCase();
    const icon  = e.is_dir ? '📁' : extIcon(ext);
    const ebCls = e.is_dir ? '' : extBadgeCls(ext);
    const relp  = fsPath ? fsPath + '/' + e.name : e.name;

    const tr = document.createElement('tr');
    tr.style.animationDelay = (i * 12) + 'ms';
    tr.innerHTML = `
      <td class="td-icon"><div class="fs-ico">${icon}</div></td>
      <td class="td-name">
        <div class="fs-name ${e.is_dir ? 'is-dir' : ''}">
          ${e.is_dir
            ? `<span class="name-text" onclick="fsNavigate('${relp.replace(/'/g,"\\'")}');event.stopPropagation()">${e.name}</span>`
            : `<span class="name-text">${e.name}</span>`
          }
          ${!e.is_dir && ext ? `<span class="ext-badge ${ebCls}">${ext}</span>` : ''}
        </div>
      </td>
      <td class="td-size">${e.is_dir ? '—' : fmtSize(e.size)}</td>
      <td class="td-modified">${e.modified_str}</td>
      <td class="td-perms">${e.perms}</td>
      <td class="td-acts">
        ${!e.is_dir
          ? `<a class="row-act" href="/fs/download?path=${encodeURIComponent(relp)}" download>⬇ dl</a>`
          : `<button class="row-act dir" onclick="fsNavigate('${relp.replace(/'/g,"\\'")}')">→ open</button>`
        }
      </td>`;
    tbody.appendChild(tr);
  });
}

// ── Helpers ───────────────────────────────────────
function extIcon(ext) {
  const m = {
    jpg:'🖼',jpeg:'🖼',png:'🖼',gif:'🖼',webp:'🖼',svg:'🖼',bmp:'🖼',ico:'🖼',
    pdf:'📄',doc:'📝',docx:'📝',txt:'📝',md:'📝',rtf:'📝',
    xls:'📊',xlsx:'📊',csv:'📊',pptx:'📑',
    zip:'🗜',rar:'🗜',gz:'🗜','7z':'🗜',tar:'🗜',
    exe:'⚙',elf:'⚙',dll:'⚙',so:'⚙',bin:'⚙',
    py:'🐍',js:'📜',ts:'📜',html:'🌐',css:'🎨',php:'🌐',
    sh:'💻',bat:'💻',ps1:'💻',
    mp4:'🎬',mov:'🎬',avi:'🎬',mkv:'🎬',
    mp3:'🎵',wav:'🎵',flac:'🎵',
    json:'{}',xml:'</>',yaml:'📋',toml:'📋',
    pem:'🔑',key:'🔑',crt:'🔑',cer:'🔑',
    db:'🗄',sql:'🗄',sqlite:'🗄',
  };
  return m[ext] || '📎';
}

function extBadgeCls(ext) {
  if (['jpg','jpeg','png','gif','webp','svg','bmp','ico'].includes(ext))       return 'ext-img';
  if (['py','js','ts','html','css','php','sh','bat','ps1','c','cpp','go','rs','rb','java'].includes(ext)) return 'ext-code';
  if (['pdf','doc','docx','txt','md','rtf','pptx','odt'].includes(ext))        return 'ext-doc';
  if (['zip','rar','gz','7z','tar','bz2'].includes(ext))                       return 'ext-arc';
  if (['exe','elf','dll','so','bin','apk'].includes(ext))                      return 'ext-exec';
  if (['mp4','mov','avi','mkv','mp3','wav','flac'].includes(ext))              return 'ext-media';
  if (['json','xml','yaml','toml','csv','xls','xlsx','db','sql','sqlite'].includes(ext)) return 'ext-data';
  return 'ext-other';
}

function fmtSize(b) {
  if (!b) return '0 B';
  if (b < 1024)       return b + ' B';
  if (b < 1048576)    return (b / 1024).toFixed(1) + ' KB';
  if (b < 1073741824) return (b / 1048576).toFixed(1) + ' MB';
  return (b / 1073741824).toFixed(2) + ' GB';
}

function toast(msg, err = false) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'show' + (err ? ' err' : '');
  clearTimeout(t._tid);
  t._tid = setTimeout(() => t.className = '', 3200);
}

loadUploads();
</script>
</body>
</html>
"""

# ── Upload routes ─────────────────────────────────────────────

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/upload', methods=['POST'])
def upload_file():
    saved = []
    for file in request.files.getlist('files'):
        if file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            saved.append(filename)
    return jsonify({'uploaded': saved})

@app.route('/files')
def list_files():
    items = []
    for f in os.listdir(UPLOAD_FOLDER):
        path = os.path.join(UPLOAD_FOLDER, f)
        if os.path.isfile(path):
            items.append({'name': f, 'size': os.path.getsize(path)})
    return jsonify(sorted(items, key=lambda x: x['name'].lower()))

@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    path = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
    if os.path.exists(path):
        os.remove(path)
        return jsonify({'deleted': filename})
    return jsonify({'error': 'not found'}), 404

@app.route('/download-all')
def download_all():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in os.listdir(UPLOAD_FOLDER):
            full = os.path.join(UPLOAD_FOLDER, f)
            if os.path.isfile(full):
                zf.write(full, f)
    buf.seek(0)
    return send_file(buf, download_name='uploads.zip', as_attachment=True, mimetype='application/zip')

# ── File Browser routes ───────────────────────────────────────

@app.route('/fs')
def fs_list():
    import stat as statmod
    relpath     = request.args.get('path', '')
    show_hidden = request.args.get('hidden', 'false').lower() == 'true'

    target = safe_path(relpath)
    if target is None or not os.path.isdir(target):
        return jsonify({'error': 'Invalid or inaccessible path'}), 400

    entries = []
    try:
        for name in sorted(os.listdir(target), key=str.lower):
            if not show_hidden and name.startswith('.'):
                continue
            full = os.path.join(target, name)
            try:
                st     = os.stat(full)
                is_dir = os.path.isdir(full)
                mtime  = datetime.datetime.fromtimestamp(st.st_mtime)
                mode   = st.st_mode
                perms  = ''
                for bits in [
                    (statmod.S_IRUSR, statmod.S_IWUSR, statmod.S_IXUSR),
                    (statmod.S_IRGRP, statmod.S_IWGRP, statmod.S_IXGRP),
                    (statmod.S_IROTH, statmod.S_IWOTH, statmod.S_IXOTH),
                ]:
                    perms += ('r' if mode & bits[0] else '-')
                    perms += ('w' if mode & bits[1] else '-')
                    perms += ('x' if mode & bits[2] else '-')

                entries.append({
                    'name':         name,
                    'is_dir':       is_dir,
                    'size':         0 if is_dir else st.st_size,
                    'modified':     st.st_mtime,
                    'modified_str': mtime.strftime('%Y-%m-%d  %H:%M'),
                    'perms':        perms,
                })
            except (PermissionError, OSError):
                continue
    except PermissionError:
        return jsonify({'error': 'Permission denied'}), 403

    path_parts = [p for p in relpath.replace('\\', '/').split('/') if p]
    return jsonify({'entries': entries, 'path_parts': path_parts})


@app.route('/fs/download')
def fs_download():
    relpath = request.args.get('path', '')
    target  = safe_path(relpath)
    if target is None or not os.path.isfile(target):
        return jsonify({'error': 'File not found'}), 404
    return send_from_directory(os.path.dirname(target), os.path.basename(target), as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
