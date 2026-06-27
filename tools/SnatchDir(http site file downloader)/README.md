# SnatchDir

A single-file Flask web app for browsing and downloading from open HTTP directory listings (Apache/nginx autoindex and table-style indexes), preserving the full subfolder structure. It adds the conveniences of a real download manager: multi-file and multi-connection parallelism, live speeds, priority ordering, pause/resume, JSON session export/import, and a per-folder file-status view.

## Features

- **Browse open directories** — point it at any open HTTP index; lazily expand subfolders on click.
- **Folder selection** — check whole folders; nested selections are de-duplicated so a parent and its child aren't both downloaded.
- **Structure preserved** — downloads mirror the remote subfolder tree on disk.
- **Sort** — by name, size, or modified date (parsed from the listing).
- **Filter** — live name search that highlights matches and auto-expands branches containing a hit.
- **Parallel downloads** — two independent dials:
  - **⚡ Workers** — how many files download at once.
  - **⛓ Splits** — connections per file (segmented byte-range download for large files; falls back to single-stream when the server doesn't support `Range` or the file is small).
- **Live transfer speeds** — per folder and total.
- **Priority** — reorder transfers with ▲/▼; higher-priority folders' files jump the queue.
- **Pause / Resume** — halt and continue in place, mid-file.
- **JSON session export/import** — save a session and resume later (across restarts); already-downloaded files are skipped.
- **Optional download location** — leave blank for `./downloads/<job_id>` or type any server-side path (`~` expands).
- **Per-folder file list** — collapsed by default; expand to see each file's status (queued / downloading / done / failed) with live counts.

## Requirements

- Python 3.8+
- See `requirements.txt` (Flask, requests, beautifulsoup4)

## Install & run

```bash
pip install -r requirements.txt
python snatchdir.py
```

Then open http://localhost:5000

## Usage

1. Paste a directory URL (e.g. `https://example.com/files/`) and click **Browse**.
2. Expand folders as needed; check the folders you want.
3. Optionally set **Save to**, **⚡ workers**, and **⛓ splits**.
4. Click **Download all**. Watch per-folder progress, speed, and the expandable file list.
5. Reorder priority with ▲/▼, **Pause**/**Resume**, or **Stop** as needed.
6. **Export** a session to JSON at any point; later use **Import…** to resume — completed files are skipped.

## How it works

- **Listing** is parsed from the index HTML. Directory links end in `/`; size and modified date are read from the text following each link, or from sibling `<td>` cells in table-style indexes.
- **Segmented download**: for files at or above 4 MB on servers advertising `Accept-Ranges: bytes`, the file is split into N byte-range segments fetched concurrently and written to their offsets in a `.part` file, then atomically renamed on completion. Smaller files or range-less servers use a single stream.
- **Resume**: files are written to a `.part` temp and only renamed when complete, so an interrupted file never counts as done. On resume, both the session's recorded completions and a live on-disk check are used to skip finished files.
- **Progress** streams to the browser over Server-Sent Events.

## HTTP API

| Method | Route | Purpose |
|---|---|---|
| GET | `/` | Web UI |
| POST | `/api/list` | List a directory (`{url}`) |
| POST | `/api/download` | Start a job (`{folders, workers, conns, dest}`) |
| POST | `/api/resume` | Resume from a session (`{state, workers, conns, dest}`) |
| GET | `/api/session/<job_id>` | Download the job's session JSON |
| POST | `/api/priority/<job_id>` | Reorder folder priority (`{order}`) |
| POST | `/api/pause/<job_id>` | Pause/resume (`{paused}`) |
| GET | `/api/progress/<job_id>` | SSE progress stream |
| POST | `/api/stop/<job_id>` | Stop a job |

## Notes & limitations

- Designed for **open** directory listings; it does not handle authentication or login walls.
- Only links within the same host and under the listing path are followed.
- The **Save to** path is resolved on the machine running the app (the server), not the browser — browsers can't pick a real filesystem path, so it's a text field.
- Resume/skip is per file; a single large file interrupted mid-transfer restarts (no partial-segment continuation).
- The bundled server runs Flask's development server. For anything beyond local single-user use, run it behind a production WSGI server (gunicorn/waitress) and restrict access.
- High `workers × splits` can trip server connection limits or look abusive — keep the product reasonable (≤ ~16–32) for public servers.

## License

Provided as-is for personal use.
