# vedit

A small Python video editor for two jobs:

1. **Keep only the stretches you want.** Give it `0.5-1.5, 2.2-4.1` and it returns a
   2.9-second clip stitched from those two pieces, audio in sync.
2. **Hide parts of the frame for a period of time.** Drag a box over the password
   that's visible between 1:12 and 1:20 and it's blurred, pixelated or blacked out
   in the exported file.

Three front ends over one engine — a browser editor, a desktop window and a
command line. They share the same `vedit` package, so an edit made in one is
reproducible in the others.

```
python serve.py --open                                # browser editor  ← start here
python vedit.py gui                                   # desktop window
python vedit.py cut clip.mp4 -o short.mp4 --keep 0.5-1.5,2.2-4.1
python vedit.py cut rec.mp4  -o safe.mp4  --box 820,640,300,56@1:12-1:20
```

---

## Install

```bash
pip install -r requirements.txt
```

That pulls in Pillow and a self-contained ffmpeg binary (`imageio-ffmpeg`, no admin
rights, nothing added to `PATH`). If you'd rather have ffmpeg system-wide:

```
winget install Gyan.FFmpeg
```

vedit looks for ffmpeg in this order: `$VEDIT_FFMPEG` → `PATH` → the bundled
binary. `ffprobe` is used when present; without it vedit reads the file by parsing
what `ffmpeg -i` prints, so the `imageio-ffmpeg` route works fine on its own.

Check what it found:

```bash
python vedit.py info myvideo.mp4
```

Need something to practise on? `python make_sample.py` builds a 30-second clip with
a burned-in timecode and a fake `PASSWORD hunter2` banner, so you can see at a
glance which parts survived the cut and whether the blur landed.

---

## The web editor

```bash
python serve.py --open              # http://127.0.0.1:5000
python vedit.py web --open          # the same thing through the CLI
```

This is the one to reach for. Because the browser plays the video itself you get
real playback and scrubbing, which the desktop window can't do — and the
rectangles you draw are blurred, pixelated or blacked out **live while it plays**,
using the same maths the exporter uses.

```
┌──────────────────────────────────────────────┬──────────────────────┐
│                                              │ KEEP THESE STRETCHES │
│          drag a box onto the video           │  1. 0:00.5 → 0:01.5  │
│          — the effect shows live             │  2. 0:02.2 → 0:04.1  │
│                                              ├──────────────────────┤
│                                              │ HIDE THESE REGIONS   │
│                                              │  1. blur 390,505 …   │
├──────────────────────────────────────────────┤  x y w h · from · to │
│ ▓▓░░▓▓▓░░░░░░░░░░░░░░░░  timeline            │  style · strength    │
├──────────────────────────────────────────────┼──────────────────────┤
│ ▶  −1s −f +f +1s  0:02.200  Set In  Set Out  │ EXPORT  ▓▓▓▓▓░░░░░   │
└──────────────────────────────────────────────┴──────────────────────┘
```

**Getting a file in.** Drag it onto the page, or `--allow-dir` a folder and pick
from it without uploading at all:

```bash
python serve.py --allow-dir "D:/recordings" --open
```

**Workflow.** Scrub, press `i` and `o` to mark a stretch, **Add In → Out**. Drag a
rectangle onto the video, set the times, pick a style, **Add region**. The panel
shows the output length as you go. **Export** streams progress and then offers the
result inline — you can watch it before downloading.

| key | does |
| --- | --- |
| `Space` | play / pause |
| `←` `→` | step one frame |
| `Shift`+`←` `→` | step one second |
| `i` / `o` | set the In / Out point |

**Projects** save as JSON and are the same format the command line reads, so you
can mark an edit up in the browser and batch it later:

```bash
python vedit.py cut clip.mp4 -o out.mp4 --project clip.vedit.json
```

### Files a browser can't play

AVI/Xvid, HEVC, ProRes and similar won't decode in a `<video>` tag. vedit notices
(both up front from the codec, and from the element's own error event) and
transcodes a small H.264 **preview copy** in the background, then swaps the player
over. Coordinates stay in *source* pixels throughout, and **the export always reads
the original file** — the proxy is only ever something to look at. Verified: a
640×480 Xvid source previewed through an 854-wide proxy still exported at 640×480
with the redaction landing on the exact pixel.

### Server options

| flag | |
| --- | --- |
| `--host` / `--port` | default `127.0.0.1:5000` |
| `--allow-dir DIR` | let the page open files under `DIR` directly (repeatable) |
| `--max-upload GB` | upload ceiling, default 8 |
| `--work-dir DIR` | where workspaces live, default your temp dir |
| `--open` | open a browser once it's up |

### A note on exposing it

It listens on localhost only, and refuses any other `--host` unless you add
`--i-know`. That's deliberate: there is **no authentication**, and the API accepts
uploads, runs ffmpeg and serves the results back. Put it behind something that
authenticates before letting anyone else reach it.

Within those bounds it is written defensively: each upload gets an unguessable id
and its own workspace, every served path is rebuilt server-side from a basename so
a request can't climb out of it, `--allow-dir` is checked against resolved paths
(so `..` doesn't escape), a file you opened in place is never deleted when you
close the job, and the one free-text field that reaches ffmpeg — the box colour —
is whitelisted to names and hex, because a filtergraph treats `:` and `,` as
syntax. There are tests for each of those.

---

## The desktop editor

```bash
python vedit.py gui                 # or double-click vedit-gui.bat on Windows
python vedit.py gui myvideo.mp4
```

No live playback here — it steps frames and has a **Quick preview** button that
renders a rough cut and opens it in your player. If you want to watch while you
edit, use the web editor above.

```
┌─────────────────────────────────────────────┬───────────────────────┐
│                                             │ Keep these stretches  │
│         the frame — drag a box here         │  1. 0:00.5 → 0:01.5   │
│         to mark something to hide           │  2. 0:02.2 → 0:04.1   │
│                                             │ [Add In→Out][Up][Down]│
│                                             ├───────────────────────┤
│                                             │ Hide these regions    │
│                                             │  1. blur 820,640 …    │
├─────────────────────────────────────────────┤ x y w h  from … to …  │
│ ▓▓▓▓░░░░░▓▓▓▓▓▓░░░░░░░░░░░░  timeline       │ style ▾  strength ──  │
├─────────────────────────────────────────────┤ [Add region][Update]  │
│ |< -1s -f +f +1s >|  0:02.200  [i] [o]      │                       │
├─────────────────────────────────────────────┴───────────────────────┤
│ Save as […]  quality 20  speed medium  [Export]  ▓▓▓▓▓▓▓░░░░░░      │
└─────────────────────────────────────────────────────────────────────┘
```

**To keep a stretch:** scrub to the start, press `i`, scrub to the end, press `o`,
then **Add In→Out**. Repeat for each piece. An empty list means "keep everything".
The list is the playback order, and **Up** / **Down** reorder it.

**To hide something:** drag a rectangle straight onto the frame. That fills in
x/y/w/h. Set **from** / **to** (or click **use In/Out**), pick a style and strength,
then **Add region**. The preview applies the effect exactly as ffmpeg will, so what
you see while scrubbing is what you get.

| key | does |
| --- | --- |
| `←` `→` | step one frame |
| `Shift`+`←` `→` | step one second |
| `Home` / `End` | jump to start / end |
| `i` / `o` | set the In / Out point |

**Quick preview** renders a fast, low-resolution version of the whole edit and opens
it in your player — worth doing before a long export. **Save project** writes the
edit to JSON so you can come back to it, or hand it to `--project` on the command
line.

---

## The command line

```
python vedit.py cut INPUT [-o OUTPUT] [options]
```

### Choosing what to keep

| flag | meaning |
| --- | --- |
| `--keep RANGES` | keep these, in the order given |
| `--drop RANGES` | keep everything *except* these |

Both take comma-separated ranges and can be repeated. Times accept
`12`, `12.5`, `350ms`, `90s`, `1:30`, `1:30.25`, `01:02:03.500` and `end`.
Either `-` or `..` separates a range.

```bash
# the example from the top: keep 0.5-1.5s and 2.2-4.1s
python vedit.py cut clip.mp4 -o short.mp4 --keep 0.5-1.5,2.2-4.1

# trim the dead air off both ends
python vedit.py cut talk.mp4 -o talk-tight.mp4 --drop 0-8,12:40-end

# keep three chapters, with a timecode-style range in the middle
python vedit.py cut demo.mp4 -o demo.mp4.out --keep 0-1:30 --keep 4:05-6:12 --keep 9:00-end
```

`--keep` preserves the order you type, so listing a later range first reorders the
video, and listing one twice repeats it. Overlapping `--drop` ranges are merged.

### Choosing what to hide

```
--blur      X,Y,W,H[@START-END][/STRENGTH]
--pixelate  X,Y,W,H[@START-END][/STRENGTH]
--box       X,Y,W,H[@START-END][/STRENGTH]
```

All three are repeatable. `X,Y` is the top-left corner in pixels from the top-left
of the frame; any of the four numbers may use `%` instead. Leave off `@START-END`
and the region is hidden for the whole clip. `STRENGTH` is 1–100 (default 25) and
scales with the size of the box, so a small region gets proportionally hidden.

```bash
# blur a fixed rectangle while the password is on screen
python vedit.py cut rec.mp4 -o safe.mp4 --blur 820,640,300,56@1:12-1:20

# black out the bottom-left eighth for the whole video, using percentages
python vedit.py cut rec.mp4 -o safe.mp4 --box 0,88%,25%,12%

# two regions at once, different styles, and trim as well
python vedit.py cut rec.mp4 -o safe.mp4 \
    --keep 0:05-2:30 \
    --pixelate 40,40,420,90@0:05-0:20/60 \
    --box 820,640,300,56@1:12-1:20
```

**Times always refer to the original video**, never to the trimmed result. That's
deliberate: you read `1:12` off the source while scrubbing, and adding a cut later
doesn't silently move your blur.

### Which style for a password?

`--box` — a solid fill. The pixels are gone.

Blur and pixelation are *lossy transformations of the original pixels*, not
deletions. Both have been reversed in practice: heavy pixelation of a known font on
a known background is a small search space, and a blur that stays still while the
background moves leaks information across frames. For a demo recording where you
just don't want a shoulder-surfer reading a token, blur is fine. For anything you'd
be unhappy to see recovered — a real credential, a key, a customer's details — use
`--box`, and check the exported file rather than the preview.

Two more habits worth having: make the box larger than the text, and check whether
the same secret appears elsewhere in the recording (a title bar, a terminal
scrollback, a notification toast) before you call it redacted.

### Encoding

| flag | default | |
| --- | --- | --- |
| `--crf N` | 20 | quality, lower is better; 18 is near-transparent, 28 is small |
| `--preset NAME` | medium | `ultrafast` … `slower`; trades speed for file size |
| `--vcodec` / `--acodec` | libx264 / aac | |
| `--ab RATE` | 192k | audio bitrate |
| `--fps N` | source | force a constant frame rate (useful for variable-rate screen recordings) |
| `--scale-width N` | — | downscale, keeping the aspect ratio |
| `--mute` | off | drop the audio |

### Other flags

| flag | |
| --- | --- |
| `--dry-run` | print the ffmpeg command and stop |
| `--project FILE` | start from a project saved in the GUI |
| `--save-project FILE` | write this edit out as JSON |
| `-q` | only errors |

`python vedit.py info FILE` prints the resolution, duration, frame rate, audio
layout and which ffmpeg is in use.

---

## Layout

```
vedit/            the engine — probing, the filtergraph, rendering
  graph.py          builds the one -filter_complex string
  model.py          Project / Segment / Redaction
webapp/           the Flask front end (validation only; no edit logic)
  app.py            routes
  jobs.py           per-upload workspaces and background tasks
serve.py          launcher for the web editor
vedit.py          launcher for the CLI and desktop GUI
```

## Using it as a library

```python
from vedit import Project, Segment, Redaction, probe, render

info = probe("recording.mp4")
project = Project(source="recording.mp4", output="clean.mp4")
project.segments = [Segment(0.5, 1.5), Segment(2.2, 4.1)]
project.redactions = [
    Redaction(x=820, y=640, w=300, h=56, start=72, end=80, mode="box"),
]
render(project, info, on_progress=lambda frac, secs: print(f"{frac:.0%}"))
```

---

## How it works

One ffmpeg process, one `-filter_complex` graph, in this order:

1. **Redact.** Each region is a `split` → `crop` → `gblur`/`scale`-down-and-up →
   `overlay`, gated by `enable='between(t,START,END)'`. A `box` is a single
   `drawbox`. These run on the full-length stream, which is what keeps your times
   anchored to the source.
2. **Trim.** `split` into one branch per kept stretch, `trim` + `setpts` each one,
   and the same with `atrim` for audio.
3. **Join.** `concat` interleaves the video and audio pairs, so sync is maintained
   by construction rather than by luck.
4. **Encode** to yuv420p H.264, with `+faststart` for mp4.

For `--keep 0.5-1.5,2.2-4.1` plus one blur, that's:

```
[0:v]split=2[rb0][rc0];
[rc0]crop=420:70:390:504,gblur=sigma=21.0:steps=3[rf0];
[rb0][rf0]overlay=390:504[vr0];
[vr0]split=2[sv0][sv1];
[sv0]trim=start=0.5000:end=1.5000,setpts=PTS-STARTPTS[tv0];
[sv1]trim=start=2.2000:end=4.1000,setpts=PTS-STARTPTS[tv1];
[0:a]asplit=2[sa0][sa1];
[sa0]atrim=start=0.5000:end=1.5000,asetpts=PTS-STARTPTS[ta0];
[sa1]atrim=start=2.2000:end=4.1000,asetpts=PTS-STARTPTS[ta1];
[tv0][ta0][tv1][ta1]concat=n=2:v=1:a=1[cv][outa];
[cv]format=yuv420p[outv]
```

Some details that matter:

- **Rectangles are snapped to even pixels** and clamped to the frame. Odd offsets
  misalign the chroma planes of yuv420p and leave a coloured fringe along the edge
  of the covered area.
- **Rotation is handled.** Phone footage carries a rotation flag; ffmpeg applies it
  before your filters see the frame, so vedit reports the *displayed* dimensions and
  your coordinates mean what they look like.
- **Audio is stream-copied when nothing touches it** (a redaction-only edit into a
  compatible container), so you don't lose a generation for no reason.
- **Cutting always re-encodes.** Frame-accurate cuts at arbitrary times can't be
  done by copying, because a cut point is rarely a keyframe.

### Speed and memory

Measured on a 5-minute 1280x720 30fps source, `-preset ultrafast`:

| edit | peak RSS | wall time |
| --- | ---: | ---: |
| 1 segment | 261 MB | 0.6 s |
| 2 segments (`0.5-1.5, 2.2-4.1`) | 260 MB | 0.2 s |
| 2 segments, far apart | 252 MB | 1.9 s |
| 6 segments spread over the clip | 261 MB | 3.4 s |
| 20 segments spread over the clip | 263 MB | 3.4 s |
| 2 segments + 3 redactions | 262 MB | 7.2 s |
| 2 segments, **reversed order** | 689 MB | 2.1 s |

Memory is flat in the number of segments — 20 costs the same as 1 — because
`concat` consumes its inputs in order and `trim` discards everything outside its
range as it streams past.

The exception is the last row. If you deliberately put a later part of the source
*earlier* in the output, `split` feeds that branch while `concat` is still busy with
another one, so those frames have to be held as raw video until their turn. vedit
estimates this up front and warns you when it would exceed 256 MB; sorting the
segments by start time makes it go away. Reordering a short clip is cheap, so this
only bites on long out-of-order edits.

---

## Tests

```bash
python -m pip install pytest
python -m pytest tests -q
```

52 tests, all against clips built on the fly:

- **33 core** — time parsing, range arithmetic, region specs, graph construction for
  every mode, and end-to-end renders. One checks the blur actually flattens detail
  rather than merely running without error.
- **19 web** — upload, Range serving (without it the `<video>` tag cannot seek),
  plan, render, cancel, and the security properties: traversal in a download name,
  a filtergraph injection in the box colour, `--allow-dir` containment, and that
  closing a job never deletes a file you opened in place.

---

## Troubleshooting

**"ffmpeg was not found"** — `pip install imageio-ffmpeg`, or point `VEDIT_FFMPEG` at
an ffmpeg executable.

**The GUI won't start.** It needs tkinter. That ships with python.org builds on
Windows and macOS; on Debian/Ubuntu it's `sudo apt install python3-tk`.

**Scrubbing feels slow.** Each seek decodes a frame. Long-GOP formats (H.265, some
4K phone footage) are slower to seek than H.264. Frames are cached, so revisiting a
spot is instant.

**The output is huge.** Lower the quality with `--crf 24` or add `--scale-width 1280`.

**The audio drifts on a screen recording.** Screen recorders often write variable
frame rate. Force a constant one with `--fps 30`.

**A blur edge shimmers.** Raise the strength, or grow the box by a few pixels —
video compression smears some detail across the boundary.

**The web page shows a black video.** The browser can't decode that codec; vedit
should build a preview copy automatically. If it doesn't, check the terminal — the
proxy transcode logs there.

**Upload is slow for a huge file.** It's a copy, even to localhost. Use
`--allow-dir` and pick the file in place instead.

**`Address already in use`.** Something else has port 5000 (on macOS, AirPlay
Receiver). Use `--port 5057`.
