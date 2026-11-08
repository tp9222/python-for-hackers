// ── Library / gallery ───────────────────────────────────────────────────────
let IMAGES = [];
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const imgUrl = m => `/api/image/${m.id}?v=${m.v || 0}`;

function showToast(msg, type='info', duration=3500) {
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  $('toast-container').appendChild(el);
  requestAnimationFrame(() => el.classList.add('show'));
  setTimeout(() => { el.classList.remove('show'); setTimeout(() => el.remove(), 300); }, duration);
}

async function api(url, opts) {
  const r = await fetch(url, opts);
  let data;
  try { data = await r.json(); } catch { data = {ok:false, error:`HTTP ${r.status}`}; }
  if (!r.ok && data.ok !== false) data = {ok:false, error:`HTTP ${r.status}`};
  return data;
}

async function loadImages() {
  const d = await api('/api/images');
  IMAGES = d.images || [];
  render();
}

function render() {
  $('count').textContent = IMAGES.length ? `${IMAGES.length} image${IMAGES.length > 1 ? 's' : ''}` : '';
  $('export-btn').toggleAttribute('hidden', !IMAGES.length);
  if (!IMAGES.length) { $('grid').innerHTML = '<div class="empty">No screenshots yet.</div>'; return; }
  $('grid').innerHTML = IMAGES.map((m, i) => `
    <div class="card" data-id="${m.id}">
      <div class="fig"><span>Figure ${i + 1}</span>${m.edited ? '<span class="badge">EDITED</span>' : ''}</div>
      <div class="thumb" onclick="openViewer('${m.id}')">
        <img src="${imgUrl(m)}" alt="${esc(m.caption || m.filename)}" loading="lazy">
        <button class="ie-swap-btn" onclick="event.stopPropagation();swapImage('${m.id}')" title="Replace with a different image (keeps caption and position)">⇄</button>
        <button class="ie-edit-btn" onclick="event.stopPropagation();editImage('${m.id}')" title="Edit: crop / highlight / red box / blur">✎</button>
      </div>
      <div class="meta">
        <div class="name" title="${esc(m.filename)}">${esc(m.filename)} · ${m.width}×${m.height}</div>
        <input class="cap" placeholder="Caption…" value="${esc(m.caption)}" maxlength="500"
               onchange="setCaption('${m.id}', this.value)">
        <div class="acts">
          <button class="btn sm" onclick="editImage('${m.id}')">✎ Edit</button>
          <button class="btn sm" onclick="move('${m.id}',-1)" ${i === 0 ? 'disabled' : ''} title="Move earlier">◀</button>
          <button class="btn sm" onclick="move('${m.id}',1)" ${i === IMAGES.length - 1 ? 'disabled' : ''} title="Move later">▶</button>
          ${m.edited ? `<button class="btn sm" onclick="revert('${m.id}')" title="Discard edits and restore the original upload">↺ Revert</button>` : ''}
          <a class="btn sm" href="/api/download/${m.id}" title="Download">⬇</a>
          <button class="btn sm danger" onclick="removeImage('${m.id}')" title="Delete">🗑</button>
        </div>
      </div>
    </div>`).join('');
}

function replaceMeta(img) {
  const i = IMAGES.findIndex(m => m.id === img.id);
  if (i >= 0) IMAGES[i] = img;
  render();
}

// -- upload: picker, drag-and-drop, clipboard paste --------------------------
async function uploadFiles(files) {
  files = [...files].filter(f => f && f.size);
  if (!files.length) return;
  const fd = new FormData();
  files.forEach((f, n) => fd.append('images', f, f.name || `pasted_${Date.now()}_${n}.png`));
  const d = await api('/api/upload', {method:'POST', body:fd});
  if (d.added && d.added.length) {
    IMAGES.push(...d.added);
    render();
    showToast(`✅ Added ${d.added.length} image${d.added.length > 1 ? 's' : ''}`, 'ok', 2000);
  }
  (d.errors || []).forEach(e => showToast('✗ ' + e, 'err', 5000));
  if (!d.ok && !(d.errors || []).length) showToast('✗ ' + (d.error || 'Upload failed'), 'err', 4000);
}

function pickFiles() {
  const input = document.createElement('input');
  input.type = 'file'; input.multiple = true;
  input.accept = 'image/png,image/jpeg,image/gif';
  input.onchange = () => uploadFiles(input.files);
  input.click();
}

// -- editing ------------------------------------------------------------------
function editImage(id) {
  const meta = IMAGES.find(m => m.id === id);
  if (!meta) return;
  ieOpen(imgUrl(meta), async cv => {
    const fd = new FormData();
    fd.append('image', await ieBlob(cv), 'edited.png');
    const d = await api(`/api/replace/${id}`, {method:'POST', body:fd});
    if (!d.ok) { showToast('✗ ' + (d.error || 'Save failed'), 'err', 4000); return false; }
    replaceMeta(d.image);
  });
}

// Swap a screenshot for a different file, keeping its id, caption and position.
function swapImage(id) {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/png,image/jpeg,image/gif';
  input.onchange = async () => {
    const file = input.files && input.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append('image', file, file.name);
    const d = await api(`/api/replace/${id}`, {method:'POST', body:fd});
    if (!d.ok) { showToast('✗ ' + (d.error || 'Replace failed'), 'err', 4000); return; }
    replaceMeta(d.image);
    showToast('✅ Screenshot replaced', 'ok', 2000);
  };
  input.click();
}

async function revert(id) {
  if (!confirm('Discard all edits and restore the original upload?')) return;
  const d = await api(`/api/revert/${id}`, {method:'POST'});
  if (!d.ok) { showToast('✗ ' + (d.error || 'Revert failed'), 'err', 4000); return; }
  replaceMeta(d.image);
  showToast('↺ Original restored', 'ok', 2000);
}

async function setCaption(id, caption) {
  const d = await api(`/api/caption/${id}`, {method:'POST', headers:{'Content-Type':'application/json'},
                                             body:JSON.stringify({caption})});
  if (!d.ok) { showToast('✗ Caption not saved', 'err', 3000); return; }
  const m = IMAGES.find(x => x.id === id);
  if (m) m.caption = caption;
}

async function move(id, delta) {
  const i = IMAGES.findIndex(m => m.id === id), j = i + delta;
  if (i < 0 || j < 0 || j >= IMAGES.length) return;
  [IMAGES[i], IMAGES[j]] = [IMAGES[j], IMAGES[i]];
  render();
  const d = await api('/api/reorder', {method:'POST', headers:{'Content-Type':'application/json'},
                                       body:JSON.stringify({order: IMAGES.map(m => m.id)})});
  if (!d.ok) { showToast('✗ ' + (d.error || 'Reorder failed'), 'err', 3000); loadImages(); }
}

async function removeImage(id) {
  const m = IMAGES.find(x => x.id === id);
  if (!m || !confirm(`Delete "${m.filename}" (original and edited copy)?`)) return;
  const d = await api(`/api/image/${id}`, {method:'DELETE'});
  if (!d.ok) { showToast('✗ Delete failed', 'err', 3000); return; }
  IMAGES = IMAGES.filter(x => x.id !== id);
  render();
}

// -- viewer ------------------------------------------------------------------
function openViewer(id) {
  const m = IMAGES.find(x => x.id === id);
  if (!m) return;
  $('viewer-img').src = imgUrl(m);
  $('viewer-cap').textContent = m.caption || m.filename;
  $('viewer').classList.add('active');
}
function closeViewer() { $('viewer').classList.remove('active'); }

document.addEventListener('DOMContentLoaded', () => {
  const drop = $('drop');
  ['dragenter', 'dragover'].forEach(t => document.addEventListener(t, e => {
    if (!e.dataTransfer || ![...e.dataTransfer.types].includes('Files')) return;
    e.preventDefault(); drop.classList.add('over');
  }));
  ['dragleave', 'drop'].forEach(t => document.addEventListener(t, e => {
    if (t === 'dragleave' && e.relatedTarget) return;
    drop.classList.remove('over');
  }));
  document.addEventListener('drop', e => {
    if (!e.dataTransfer || !e.dataTransfer.files.length) return;
    e.preventDefault();
    if (!ieActive()) uploadFiles(e.dataTransfer.files);
  });
  document.addEventListener('paste', e => {
    if (ieActive() || (e.target && e.target.matches && e.target.matches('input, textarea'))) return;
    const files = [...(e.clipboardData?.items || [])]
      .filter(it => it.kind === 'file' && it.type.startsWith('image/')).map(it => it.getAsFile());
    if (files.length) { e.preventDefault(); uploadFiles(files); }
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeViewer(); });
  loadImages();
});
