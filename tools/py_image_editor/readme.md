# Screenshot Editor

A small Flask app for editing screenshots in the browser: crop, highlight, red box and blur.
The original upload is never overwritten.

## Run

```bash
python -m pip install -r requirements.txt
python app.py                      # http://127.0.0.1:5070
python app.py --port 8080 --data D:\shots
```

You can also double-click `run.bat`, which installs Flask, opens the browser and starts the server.

## Editor

| Tool | What it does |
|---|---|
| ✂ Crop | Drag a rectangle. The area outside it is dimmed while you drag, and the crop happens on release. |
| 🖍 Highlight | Yellow wash, `rgba(255,230,0,0.35)`. |
| ▢ Red Box | `#e00000` outline. The line width is `max(3, longest side / 250)`, so it stays visible when the image is shrunk down. |
| 🌫 Blur | Redaction: pixelate at 1/14 size, blur that copy, then add a 10 % grey wash. Downscaling throws the detail away, so it can't be sharpened back. For real secrets, a Red Box or a crop is still safer. |

- Undo (Ctrl+Z) and Reset.
- Zoom with − / + / Fit, Ctrl+wheel (zooms around the cursor), or the `+`, `-` and `0` keys.
- `F` toggles full screen and `Esc` cancels.
- These shortcuts are new here: `C`, `H`, `R` and `B` pick a tool, and Ctrl+S saves.
- Edits are made at full resolution. Zoom only changes how big the image looks on screen.

## Library

- Add images with the button, by dragging them onto the page, or with **Ctrl+V** from the clipboard.
- **✎ Edit** saves the canvas as a PNG under `data/edited/`. The upload in `data/originals/` is never changed.
- **⇄ Swap** replaces an image with a different file. The id, caption and position (the figure number) stay the same.
- **↺ Revert** throws away the edited copy and brings back the original.
- File types are checked by their magic bytes (PNG, JPEG or GIF), and the extension is taken from the bytes. A renamed text file is refused, and a failed replacement leaves the current image as it was.
- You can add captions, reorder images with ◀ ▶, download one image, or **Export all**. The export is a zip named by figure number (`01_…`, `02_…`) plus a `captions.csv`.

The server listens on `127.0.0.1` only. Use `--host 0.0.0.0` to open it to your LAN, but there is no authentication.

## Tests

```bash
python -m pytest -q tests
```
