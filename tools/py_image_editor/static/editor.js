// ── Image editor: crop / highlight / red box / blur (client-side canvas) ──
//
// ieOpen(src, onSave): onSave(canvas) persists the edit and returns false on failure.
const IE = {tool:'box', hist:[], orig:null, drag:null, base:null, onSave:null, zoom:1};
const ieCv = () => document.getElementById('ie-canvas');
const ieActive = () => document.getElementById('ie-overlay').classList.contains('active');

function ieTool(t) {
  IE.tool = t;
  ['crop','hl','box','blur'].forEach(k => document.getElementById('ie-t-'+k).classList.toggle('active', k === t));
}

function ieOpen(src, onSave) {
  const img = new Image();
  img.onload = () => {
    const cv = ieCv();
    cv.width = img.naturalWidth; cv.height = img.naturalHeight;
    cv.getContext('2d').drawImage(img, 0, 0);
    Object.assign(IE, {hist:[], drag:null, onSave});
    IE.orig = ieSnap();
    ieTool(IE.tool);
    ieDims();
    document.getElementById('ie-overlay').classList.add('active');
    ieFit();   // after the overlay is shown, so the stage has a measurable size
  };
  img.onerror = () => showToast('✗ Could not load image for editing', 'err', 3000);
  img.src = src;
}

function ieClose() {
  document.getElementById('ie-overlay').classList.remove('active');
  Object.assign(IE, {hist:[], orig:null, drag:null, base:null, onSave:null});
}

function ieDims() {
  const cv = ieCv(), el = document.getElementById('ie-dims');
  if (el) el.textContent = `${cv.width} × ${cv.height}px`;
}
function ieSnap() { const cv = ieCv(); return cv.getContext('2d').getImageData(0, 0, cv.width, cv.height); }
function ieRestore(d) { const cv = ieCv(); cv.width = d.width; cv.height = d.height; cv.getContext('2d').putImageData(d, 0, 0); ieApplyZoom(); ieDims(); }

// -- Zoom / full screen ------------------------------------------------------
// The canvas keeps its true pixel size; only its CSS size changes, so edits stay
// at full resolution and iePt's rect-ratio mapping keeps working at any zoom.
function ieApplyZoom() {
  const cv = ieCv();
  if (!cv || !IE.zoom) return;
  cv.style.width  = Math.round(cv.width  * IE.zoom) + 'px';
  cv.style.height = Math.round(cv.height * IE.zoom) + 'px';
  const label = document.getElementById('ie-zoom-label');
  if (label) label.textContent = Math.round(IE.zoom * 100) + '%';
}

function ieSetZoom(z, anchor) {
  const cv = ieCv(), wrap = cv.parentElement;
  const next = Math.min(8, Math.max(0.05, z));
  const prev = IE.zoom || 1;
  // Keep the point under the cursor (or the view centre) fixed while zooming.
  const ax = anchor ? anchor.x : wrap.scrollLeft + wrap.clientWidth / 2;
  const ay = anchor ? anchor.y : wrap.scrollTop + wrap.clientHeight / 2;
  IE.zoom = next;
  ieApplyZoom();
  const ratio = next / prev;
  wrap.scrollLeft = Math.max(0, ax * ratio - (anchor ? anchor.cx : wrap.clientWidth / 2));
  wrap.scrollTop  = Math.max(0, ay * ratio - (anchor ? anchor.cy : wrap.clientHeight / 2));
}

function ieZoomBy(factor) { ieSetZoom((IE.zoom || 1) * factor); }

function ieFit() {
  const cv = ieCv(), wrap = cv.parentElement;
  const availW = wrap.clientWidth - 40, availH = wrap.clientHeight - 24;
  if (availW <= 0 || availH <= 0 || !cv.width || !cv.height) { IE.zoom = 1; ieApplyZoom(); return; }
  IE.zoom = Math.min(1, availW / cv.width, availH / cv.height);   // never upscale past 100%
  ieApplyZoom();
  wrap.scrollLeft = wrap.scrollTop = 0;
}

function ieToggleFull() {
  const modal = document.querySelector('#ie-overlay .ie-modal');
  const full = modal.classList.toggle('ie-full');
  const btn = document.getElementById('ie-full-btn');
  if (btn) { btn.textContent = full ? '✕' : '⛶'; btn.title = full ? 'Exit full screen (F)' : 'Full screen (F)'; }
  setTimeout(ieFit, 0);   // re-fit once the modal has resized
}
function ieUndo() { if (!IE.hist.length) { showToast('Nothing to undo', 'info', 1500); return; } ieRestore(IE.hist.pop()); }
function ieReset() { if (IE.orig) { IE.hist.push(ieSnap()); ieRestore(IE.orig); } }
const ieBlob = cv => new Promise(res => cv.toBlob(res, 'image/png'));

// Mouse position → image pixel coordinates (canvas is CSS-scaled to fit)
function iePt(e) {
  const cv = ieCv(), r = cv.getBoundingClientRect();
  // A hidden or not-yet-laid-out canvas reports a zero-size rect; scaling by it would
  // divide by zero and feed NaN coordinates into every draw.
  const sx = r.width  ? cv.width  / r.width  : 1;
  const sy = r.height ? cv.height / r.height : 1;
  return {
    x: Math.max(0, Math.min(cv.width,  (e.clientX - r.left) * sx)),
    y: Math.max(0, Math.min(cv.height, (e.clientY - r.top)  * sy)),
  };
}
function ieRect(a, b) { return {x:Math.min(a.x,b.x), y:Math.min(a.y,b.y), w:Math.abs(a.x-b.x), h:Math.abs(a.y-b.y)}; }
const ieValidRect = r => r && [r.x, r.y, r.w, r.h].every(Number.isFinite) && r.w >= 1 && r.h >= 1;
// Stroke width scales with image size so boxes stay visible when the image is shrunk
function ieLW() { const cv = ieCv(); return Math.max(3, Math.round(Math.max(cv.width, cv.height) / 250)); }

// Redaction blur: pixelate first, then blur the pixelated copy, then a light grey
// wash. Downscaling destroys the detail outright (a CSS blur alone can be reversed
// by sharpening), so what is left is a ~10% ghost of the original — enough to show
// something was there, not enough to read a token, password or client name.
function ieBlurRegion(ctx, r) {
  if (!ieValidRect(r)) return;
  const x = Math.round(r.x), y = Math.round(r.y);
  const w = Math.max(1, Math.round(r.w)), h = Math.max(1, Math.round(r.h));
  const sw = Math.max(1, Math.round(w / 14)), sh = Math.max(1, Math.round(h / 14));
  const off = document.createElement('canvas');
  off.width = sw; off.height = sh;
  off.getContext('2d').drawImage(ctx.canvas, x, y, w, h, 0, 0, sw, sh);
  ctx.save();
  ctx.beginPath(); ctx.rect(x, y, w, h); ctx.clip();   // keep the blur inside the selection
  ctx.filter = `blur(${Math.max(2, Math.round(Math.min(w, h) / 10))}px)`;
  ctx.drawImage(off, 0, 0, sw, sh, x, y, w, h);
  ctx.filter = 'none';
  ctx.fillStyle = 'rgba(127,127,127,0.10)';
  ctx.fillRect(x, y, w, h);
  ctx.restore();
}

function ieDraw(ctx, tool, r, preview) {
  if (!ieValidRect(r)) return;
  ctx.save();
  try {
  if (tool === 'hl') {
    ctx.fillStyle = 'rgba(255,230,0,0.35)';
    ctx.fillRect(r.x, r.y, r.w, r.h);
  } else if (tool === 'box') {
    ctx.strokeStyle = '#e00000'; ctx.lineWidth = ieLW();
    ctx.strokeRect(r.x, r.y, r.w, r.h);
  } else if (tool === 'blur') {
    ieBlurRegion(ctx, r);
  } else if (tool === 'crop' && preview) {
    const W = ctx.canvas.width, H = ctx.canvas.height;
    ctx.fillStyle = 'rgba(0,0,0,0.45)';
    ctx.fillRect(0, 0, W, r.y);
    ctx.fillRect(0, r.y + r.h, W, H - r.y - r.h);
    ctx.fillRect(0, r.y, r.x, r.h);
    ctx.fillRect(r.x + r.w, r.y, W - r.x - r.w, r.h);
    ctx.setLineDash([ieLW()*2, ieLW()]); ctx.strokeStyle = '#fff'; ctx.lineWidth = Math.max(1, ieLW()/2);
    ctx.strokeRect(r.x, r.y, r.w, r.h);
  }
  } finally { ctx.restore(); }   // never leave a clip or filter on the canvas
}

function ieCommit(r) {
  const ctx = ieCv().getContext('2d');
  ctx.putImageData(IE.base, 0, 0);
  if (r.w < 4 || r.h < 4) return;   // ignore stray clicks
  IE.hist.push(IE.base);
  if (IE.tool === 'crop') ieRestore(ctx.getImageData(Math.round(r.x), Math.round(r.y), Math.round(r.w), Math.round(r.h)));
  else ieDraw(ctx, IE.tool, r, false);
}

async function ieSave(btn) {
  if (!IE.hist.length || !IE.onSave) { ieClose(); return; }
  if (btn) btn.disabled = true;
  try {
    if (await IE.onSave(ieCv()) === false) return;
    ieClose();
    showToast('✅ Screenshot updated', 'ok', 2000);
  } catch(e) {
    showToast('✗ Save error: ' + e, 'err', 4000);
  } finally { if (btn) btn.disabled = false; }
}

document.addEventListener('DOMContentLoaded', () => {
  const cv = ieCv();
  if (!cv) return;
  // Pointer events: drag to draw, with pen and touch support.
  cv.addEventListener('pointerdown', e => {
    if (e.button !== 0) return;
    e.preventDefault(); IE.base = ieSnap(); IE.drag = iePt(e);
  });
  window.addEventListener('pointermove', e => {
    if (!IE.drag) return;
    const ctx = cv.getContext('2d');
    ctx.putImageData(IE.base, 0, 0);
    ieDraw(ctx, IE.tool, ieRect(IE.drag, iePt(e)), true);
  });
  window.addEventListener('pointerup', e => {
    if (!IE.drag) return;
    const r = ieRect(IE.drag, iePt(e));
    IE.drag = null;
    ieCommit(r);
  });
  document.addEventListener('keydown', e => {
    if (!ieActive()) return;
    const k = e.key.toLowerCase(), mod = e.ctrlKey || e.metaKey;
    if (e.key === 'Escape') { e.stopImmediatePropagation(); ieClose(); }
    else if (mod && k === 'z') { e.preventDefault(); ieUndo(); }
    else if (mod && k === 's') { e.preventDefault(); ieSave(document.querySelector('.ie-foot .primary')); }
    else if (mod) return;
    else if (e.key === '+' || e.key === '=') { e.preventDefault(); ieZoomBy(1.25); }
    else if (e.key === '-' || e.key === '_') { e.preventDefault(); ieZoomBy(1/1.25); }
    else if (e.key === '0') { e.preventDefault(); ieFit(); }
    else if (k === 'f') { e.preventDefault(); ieToggleFull(); }
    else if ({c:'crop', h:'hl', r:'box', b:'blur'}[k]) { e.preventDefault(); ieTool({c:'crop', h:'hl', r:'box', b:'blur'}[k]); }
  }, true);

  // Ctrl/Cmd + wheel zooms about the pointer; a plain wheel scrolls (pans) as usual.
  cv.parentElement.addEventListener('wheel', e => {
    if (!e.ctrlKey && !e.metaKey) return;
    e.preventDefault();
    const wrap = cv.parentElement, box = wrap.getBoundingClientRect();
    const cx = e.clientX - box.left, cy = e.clientY - box.top;
    ieSetZoom((IE.zoom || 1) * (e.deltaY < 0 ? 1.15 : 1/1.15),
              {x: wrap.scrollLeft + cx, y: wrap.scrollTop + cy, cx, cy});
  }, {passive:false});

  window.addEventListener('resize', () => { if (ieActive()) ieApplyZoom(); });
});
