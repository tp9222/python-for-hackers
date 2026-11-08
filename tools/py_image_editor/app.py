"""Screenshot editor — a small Flask app for cropping, highlighting, boxing and blurring screenshots.

The editing itself (crop / highlight / red box / blur, undo, zoom) runs on a canvas in
the browser. This server
keeps the image library:

* uploads are validated by their magic bytes (PNG / JPEG / GIF), never by extension;
* an edit or a swap writes a NEW file under data/edited/ — the original upload under
  data/originals/ is never touched, so "Revert" can always bring it back;
* every image keeps its id, caption and position across edits and swaps.

Run:  python app.py            (http://127.0.0.1:5070)
      python app.py --port 8080 --data D:\\shots
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import struct
import threading
import time
import uuid
import zipfile
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file

BASE_DIR = Path(__file__).resolve().parent
MIMES = {".png": "image/png", ".jpg": "image/jpeg", ".gif": "image/gif"}
ID_RE = re.compile(r"^[a-f0-9]{12}$")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024   # one upload request, all files

LOCK = threading.Lock()
DATA_DIR: Path = BASE_DIR / "data"


# ── image helpers ────────────────────────────────────────────────────────────

def sniff_image_ext(head: bytes) -> str | None:
    """Return .png/.jpg/.gif from the file's own magic bytes, or None if it isn't one.

    A text file renamed .png must not land in the library, and a PNG saved as .jpg is
    what breaks a picture once it reaches Word, so the extension always comes from here.
    """
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if head[:2] == b"\xff\xd8":
        return ".jpg"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    return None


def image_size(path: Path) -> tuple[int, int]:
    """Width/height for PNG, JPEG and GIF using only the stdlib (0, 0 if unreadable)."""
    try:
        data = path.read_bytes()
    except OSError:
        return 0, 0
    ext = sniff_image_ext(data[:12])
    try:
        if ext == ".png" and len(data) >= 24:
            return struct.unpack(">II", data[16:24])
        if ext == ".gif" and len(data) >= 10:
            return struct.unpack("<HH", data[6:10])
        if ext == ".jpg":
            i = 2
            while i + 9 < len(data):
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:   # no length field
                    i += 2
                    continue
                seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
                # SOF0..SOF15, except DHT (C4), JPG (C8) and DAC (CC)
                if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                    h, w = struct.unpack(">HH", data[i + 5:i + 9])
                    return w, h
                i += 2 + seg_len
    except struct.error:
        pass
    return 0, 0


# ── library (manifest + files) ───────────────────────────────────────────────

def manifest_path() -> Path:
    return DATA_DIR / "library.json"


def load_lib() -> list[dict]:
    try:
        return json.loads(manifest_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def save_lib(lib: list[dict]) -> None:
    tmp = manifest_path().with_suffix(".tmp")
    tmp.write_text(json.dumps(lib, indent=2), encoding="utf-8")
    tmp.replace(manifest_path())          # atomic: a crash never leaves half a manifest


def find(lib: list[dict], img_id: str) -> dict:
    if not ID_RE.match(img_id or ""):
        abort(404)
    entry = next((e for e in lib if e["id"] == img_id), None)
    if entry is None:
        abort(404)
    return entry


def public(e: dict) -> dict:
    return {k: e[k] for k in ("id", "filename", "caption", "width", "height", "v")} | {
        "edited": e["path"] != e["original_path"]}


def stage_upload(storage, dest_dir: Path, stem: str) -> tuple[Path | None, str | None]:
    """Save an uploaded file under dest_dir/<stem><real ext>. Returns (path, error)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    staged = dest_dir / f"{stem}.incoming"
    storage.save(str(staged))
    with open(staged, "rb") as fh:
        ext = sniff_image_ext(fh.read(12))
    if ext is None:
        staged.unlink(missing_ok=True)
        return None, "isn't a PNG, JPEG or GIF image"
    dest = dest_dir / f"{stem}{ext}"
    dest.unlink(missing_ok=True)
    staged.replace(dest)
    return dest, None


def rel(p: Path) -> str:
    return p.relative_to(DATA_DIR).as_posix()


def absp(r: str) -> Path:
    return DATA_DIR / r


# ── routes ───────────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/images")
def api_images():
    with LOCK:
        return jsonify({"ok": True, "images": [public(e) for e in load_lib()]})


@app.post("/api/upload")
def api_upload():
    files = request.files.getlist("images")
    if not files:
        return jsonify({"ok": False, "error": "No files received"})
    added, errors = [], []
    for f in files:
        name = Path(f.filename or "pasted.png").name
        img_id = uuid.uuid4().hex[:12]
        dest, err = stage_upload(f, DATA_DIR / "originals", img_id)
        if err:
            errors.append(f"{name}: {err}")
            continue
        w, h = image_size(dest)
        entry = {"id": img_id, "filename": f"{Path(name).stem}{dest.suffix}", "caption": "",
                 "path": rel(dest), "original_path": rel(dest), "mime": MIMES[dest.suffix],
                 "width": w, "height": h, "v": int(time.time() * 1000)}
        with LOCK:
            lib = load_lib()
            lib.append(entry)
            save_lib(lib)
        added.append(public(entry))
    return jsonify({"ok": bool(added), "added": added, "errors": errors,
                    "error": "; ".join(errors) if errors and not added else None})


@app.get("/api/image/<img_id>")
def api_image(img_id):
    """The current version (edited copy if any); ?original=1 for the untouched upload."""
    with LOCK:
        e = find(load_lib(), img_id)
    p = absp(e["original_path"] if request.args.get("original") else e["path"])
    if not p.is_file():
        abort(404)
    resp = send_file(p, mimetype=MIMES.get(p.suffix, "application/octet-stream"))
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/api/download/<img_id>")
def api_download(img_id):
    with LOCK:
        e = find(load_lib(), img_id)
    return send_file(absp(e["path"]), as_attachment=True, download_name=e["filename"])


@app.post("/api/replace/<img_id>")
def api_replace(img_id):
    """Store an edited canvas PNG, or swap in a different file, for one image.

    The result goes to data/edited/; the original upload is left untouched. The image
    keeps its id, caption and position, so anything numbered by position survives.
    """
    f = request.files.get("image")
    if f is None:
        return jsonify({"ok": False, "error": "image required"})
    with LOCK:
        find(load_lib(), img_id)          # 404 before touching the disk
    # A new file name per save: the old edited copy is only removed once the new one
    # is safely in place, so a bad upload can never clobber a good screenshot.
    dest, err = stage_upload(f, DATA_DIR / "edited", f"{img_id}_{int(time.time()*1000)}")
    if err:
        return jsonify({"ok": False, "error": f"That file {err} — the screenshot was left unchanged."})
    w, h = image_size(dest)
    with LOCK:
        lib = load_lib()
        e = find(lib, img_id)
        previous = e["path"]
        e.update({"path": rel(dest), "mime": MIMES[dest.suffix], "width": w, "height": h,
                  "filename": f"{Path(e['filename']).stem}{dest.suffix}",
                  "v": int(time.time() * 1000)})
        save_lib(lib)
    if previous != e["original_path"]:
        absp(previous).unlink(missing_ok=True)     # never the original upload
    return jsonify({"ok": True, "image": public(e)})


@app.post("/api/revert/<img_id>")
def api_revert(img_id):
    with LOCK:
        lib = load_lib()
        e = find(lib, img_id)
        previous = e["path"]
        if previous == e["original_path"]:
            return jsonify({"ok": True, "image": public(e)})
        orig = absp(e["original_path"])
        w, h = image_size(orig)
        e.update({"path": e["original_path"], "mime": MIMES[orig.suffix], "width": w, "height": h,
                  "filename": f"{Path(e['filename']).stem}{orig.suffix}",
                  "v": int(time.time() * 1000)})
        save_lib(lib)
    absp(previous).unlink(missing_ok=True)
    return jsonify({"ok": True, "image": public(e)})


@app.post("/api/caption/<img_id>")
def api_caption(img_id):
    caption = str((request.get_json(silent=True) or {}).get("caption", ""))[:500]
    with LOCK:
        lib = load_lib()
        find(lib, img_id)["caption"] = caption
        save_lib(lib)
    return jsonify({"ok": True})


@app.post("/api/reorder")
def api_reorder():
    order = (request.get_json(silent=True) or {}).get("order") or []
    with LOCK:
        lib = load_lib()
        by_id = {e["id"]: e for e in lib}
        if sorted(order) != sorted(by_id):
            return jsonify({"ok": False, "error": "order must list every image exactly once"})
        save_lib([by_id[i] for i in order])
    return jsonify({"ok": True})


@app.delete("/api/image/<img_id>")
def api_delete(img_id):
    with LOCK:
        lib = load_lib()
        e = find(lib, img_id)
        lib.remove(e)
        save_lib(lib)
    for r in {e["path"], e["original_path"]}:
        absp(r).unlink(missing_ok=True)
    return jsonify({"ok": True})


@app.get("/api/export")
def api_export():
    """Every current image as a zip, named by position, plus captions.csv."""
    with LOCK:
        lib = load_lib()
    buf = io.BytesIO()
    rows = io.StringIO()
    writer = csv.writer(rows)
    writer.writerow(["figure", "file", "caption", "edited"])
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for n, e in enumerate(lib, 1):
            stem = re.sub(r"[^A-Za-z0-9_\-. ]", "_", Path(e["filename"]).stem)[:60] or "image"
            name = f"{n:02d}_{stem}{Path(e['path']).suffix}"
            p = absp(e["path"])
            if p.is_file():
                zf.write(p, name)
                writer.writerow([n, name, e["caption"], e["path"] != e["original_path"]])
        zf.writestr("captions.csv", rows.getvalue())
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name=f"screenshots_{time.strftime('%Y%m%d_%H%M%S')}.zip")


@app.errorhandler(413)
def too_large(_):
    return jsonify({"ok": False, "error": "Upload too large (64 MB per request)"}), 413


def configure(data_dir: Path) -> None:
    global DATA_DIR
    DATA_DIR = Path(data_dir).resolve()
    for sub in ("originals", "edited"):
        (DATA_DIR / sub).mkdir(parents=True, exist_ok=True)
    if not manifest_path().exists():
        save_lib([])


def main() -> None:
    ap = argparse.ArgumentParser(description="Screenshot editor (crop / highlight / red box / blur)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5070)
    ap.add_argument("--data", default=str(BASE_DIR / "data"), help="library folder")
    args = ap.parse_args()
    configure(Path(args.data))
    print(f"Screenshot editor on http://{args.host}:{args.port}  (library: {DATA_DIR})")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


configure(DATA_DIR)

if __name__ == "__main__":
    main()
