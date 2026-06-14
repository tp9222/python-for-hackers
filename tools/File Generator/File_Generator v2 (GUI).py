#!/usr/bin/env python3
"""
filegen.py — Valid File Generator for Upload Testing
Generates structurally valid files of any size for testing
web application upload functionality.

Formats: EXE, CSV, DOC, JPG, JPEG, PNG, MP4
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import struct, zlib, os, threading, time, io, zipfile
from pathlib import Path
from datetime import datetime

# ─── Colours ──────────────────────────────────────────────────────────────────
BG      = "#0d1117"
SF      = "#161b22"
BD      = "#30363d"
RED     = "#e74c3c"
GREEN   = "#39d353"
BLUE    = "#58a6ff"
YELLOW  = "#f0c040"
MUTED   = "#8b949e"
TEXT    = "#e6edf3"
FONT    = "Consolas"

CHUNK   = 512 * 1024   # 512 KB write buffer

# ─── Size helpers ─────────────────────────────────────────────────────────────
UNITS = {"KB": 1024, "MB": 1024**2, "GB": 1024**3}

def to_bytes(value: float, unit: str) -> int:
    return max(1, int(value * UNITS[unit]))

def human(n: int) -> str:
    for u in ["GB","MB","KB"]:
        if n >= UNITS[u]:
            return f"{n/UNITS[u]:.2f} {u}"
    return f"{n} B"

# ─── Generators ───────────────────────────────────────────────────────────────

def gen_jpeg(path: str, size: int, cb):
    """
    Valid JPEG: SOI + APP0 (JFIF) header, padded with
    JPEG Comment (FF FE) segments, closed with EOI.
    Comment segments can hold up to 65533 bytes each.
    Most validators, browsers, and image tools accept this structure.
    """
    with open(path, "wb") as f:
        # SOI
        f.write(b"\xff\xd8")
        # APP0 JFIF
        app0_payload = b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        f.write(b"\xff\xe0")
        f.write(struct.pack(">H", len(app0_payload) + 2))
        f.write(app0_payload)
        written = 2 + 2 + 2 + len(app0_payload)   # SOI + marker + len + payload

        # Fill with COM (comment) blocks — each holds max 65533 bytes
        MAX_PAY = 65533
        pad     = b"\x58" * MAX_PAY           # 'X'
        while written < size - 2:             # reserve 2 for EOI
            remaining = size - written - 2    # bytes left before EOI
            payload   = min(remaining - 4, MAX_PAY)  # -4 for marker+length fields
            if payload <= 0:
                break
            f.write(b"\xff\xfe")
            f.write(struct.pack(">H", payload + 2))
            # Write in sub-chunks for memory efficiency
            left = payload
            while left > 0:
                block = min(left, CHUNK)
                f.write(pad[:block])
                left -= block
            written += 4 + payload
            cb(written / size)
        # EOI
        f.write(b"\xff\xd9")


def gen_png(path: str, size: int, cb):
    """
    Valid PNG: signature + IHDR (1×1 RGB) + IDAT (real compressed pixel)
    + repeated tEXt chunks for padding + IEND.
    All chunks have correct CRC32. Passes libpng validation.
    """
    def chunk(ctype: bytes, data: bytes) -> bytes:
        body = ctype + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    with open(path, "wb") as f:
        sig = b"\x89PNG\r\n\x1a\n"
        f.write(sig)
        written = len(sig)

        # IHDR: 1×1, 8-bit RGB
        ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        f.write(ihdr);  written += len(ihdr)

        # IDAT: compressed 1×1 red pixel (filter=0, R=255, G=0, B=0)
        idat = chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
        f.write(idat);  written += len(idat)

        # IEND size: 12 bytes (len+type+crc)
        IEND = chunk(b"IEND", b"")
        IEND_SZ = len(IEND)

        # Pad with tEXt chunks (keyword + null + text)
        keyword  = b"Comment\x00"
        MAX_TEXT = 60000
        pad      = b"\x58" * MAX_TEXT
        txt_body = keyword + pad
        txt_chk  = chunk(b"tEXt", txt_body)   # pre-built full chunk

        while written < size - IEND_SZ:
            remain   = size - written - IEND_SZ
            overhead = 12                       # len(4)+type(4)+crc(4)
            avail    = remain - overhead
            if avail < len(keyword) + 1:
                break
            if avail >= len(txt_body):
                f.write(txt_chk)
                written += len(txt_chk)
            else:
                body = keyword + b"\x58" * (avail - len(keyword))
                f.write(chunk(b"tEXt", body))
                written += overhead + len(body)
            cb(written / size)

        f.write(IEND)


def gen_mp4(path: str, size: int, cb):
    """
    Valid MP4: ftyp box declaring mp42/isom brands,
    followed by a single mdat box padded to target size.
    Recognised by VLC, ffprobe, and most CDN processors.
    """
    with open(path, "wb") as f:
        # ftyp box (24 bytes)
        ftyp = (struct.pack(">I", 24) + b"ftyp"
                + b"mp42" + struct.pack(">I", 0)
                + b"mp42" + b"isom")
        f.write(ftyp)
        written = len(ftyp)

        # mdat box — fill remainder
        mdat_total = size - written
        f.write(struct.pack(">I", mdat_total))
        f.write(b"mdat")
        written += 8

        left = mdat_total - 8
        buf  = b"\x00" * CHUNK
        while left > 0:
            block = min(left, CHUNK)
            f.write(buf[:block])
            left    -= block
            written += block
            cb(written / size)


def gen_exe(path: str, size: int, cb):
    """
    Valid PE32 (x86) executable: complete MZ DOS header, DOS stub,
    PE signature, COFF header, optional header, one .text section.
    The section raw data is padded with INT3 (0xCC) — standard filler
    used by compilers/linkers. Opens in PE Explorer, dumpbin, etc.
    """
    with open(path, "wb") as f:
        PE_OFFSET = 0x80   # where PE header starts

        # ── DOS header (64 bytes) ────────────────────────────────────────────
        dos = bytearray(64)
        dos[0:2]   = b"MZ"
        dos[2:4]   = struct.pack("<H", size % 512)          # bytes on last page
        dos[4:6]   = struct.pack("<H", min(0xFFFF, max(1, (size + 511) >> 9)))  # total pages (16-bit field, legacy/ignored)
        dos[8:10]  = struct.pack("<H", 4)                   # header paragraphs
        dos[12:14] = struct.pack("<H", 0xFFFF)              # max alloc
        dos[16:18] = struct.pack("<H", 0xB8)                # initial SP
        dos[60:64] = struct.pack("<I", PE_OFFSET)           # e_lfanew
        f.write(bytes(dos))

        # ── DOS stub (prints "not DOS" message if run in DOS) ────────────────
        stub = (b"\x0e\x1f\xba\x0e\x00\xb4\x09\xcd\x21\xb8\x01\x4c\xcd\x21"
                b"This program cannot be run in DOS mode.\r\r\n$")
        stub += b"\x00" * (PE_OFFSET - 64 - len(stub))
        f.write(stub)

        # ── PE signature ─────────────────────────────────────────────────────
        f.write(b"PE\x00\x00")

        # ── COFF header (20 bytes) ───────────────────────────────────────────
        NUM_SECTIONS = 1
        f.write(struct.pack("<HHIIIHH",
            0x014C,            # Machine: x86
            NUM_SECTIONS,      # NumberOfSections
            int(time.time()),  # TimeDateStamp
            0,                 # PointerToSymbolTable
            0,                 # NumberOfSymbols
            0xE0,              # SizeOfOptionalHeader (PE32)
            0x0102,            # Characteristics: executable + 32-bit
        ))

        # ── Optional header PE32 (224 bytes) ─────────────────────────────────
        SEC_ALIGN  = 0x1000     # section alignment (4 KB)
        FILE_ALIGN = 0x200      # file alignment (512 bytes)
        SECT_VA    = 0x1000     # first section virtual address
        SECT_SIZE  = max(SEC_ALIGN, size - (PE_OFFSET + 4 + 20 + 224 + 40))
        SECT_SIZE  = (SECT_SIZE + FILE_ALIGN - 1) & ~(FILE_ALIGN - 1)
        IMAGE_SIZE = SECT_VA + ((SECT_SIZE + SEC_ALIGN - 1) & ~(SEC_ALIGN - 1))

        f.write(struct.pack("<HBB",   0x010B, 14, 0))          # Magic, LinkerVer
        f.write(struct.pack("<III",   SECT_SIZE, 0, 0))         # SizeOfCode/Init/Uninit
        f.write(struct.pack("<II",    SECT_VA, SECT_VA))        # EntryPoint, BaseOfCode
        f.write(struct.pack("<II",    0, 0x00400000))           # BaseOfData, ImageBase
        f.write(struct.pack("<II",    SEC_ALIGN, FILE_ALIGN))   # Alignments
        f.write(struct.pack("<HHHH",  6, 0, 0, 0))              # OS/Image version
        f.write(struct.pack("<HH",    5, 2))                    # SubsystemVersion
        f.write(struct.pack("<I",     0))                       # Win32VersionValue
        f.write(struct.pack("<III",   IMAGE_SIZE, PE_OFFSET + 4 + 20 + 224 + 40, 0))  # sizes
        f.write(struct.pack("<HH",    0x0003, 0))               # Subsystem=GUI, DLL flags
        f.write(struct.pack("<IIIII", 0x100000, 0x1000, 0x100000, 0x1000, 0))
        f.write(struct.pack("<I",     16))                      # NumberOfRvaAndSizes
        f.write(b"\x00" * 128)                                  # DataDirectory (16×8)

        # ── Section header: .text ─────────────────────────────────────────────
        sect_off = (PE_OFFSET + 4 + 20 + 224 + 40 + FILE_ALIGN - 1) & ~(FILE_ALIGN - 1)
        f.write(struct.pack("<8sIIIIIIHHI",
            b".text\x00\x00\x00",
            SECT_SIZE,     # VirtualSize
            SECT_VA,       # VirtualAddress
            SECT_SIZE,     # SizeOfRawData
            sect_off,      # PointerToRawData
            0, 0, 0, 0,    # relocations/linenumbers
            0x60000020,    # Characteristics: code, exec, read
        ))

        # ── Pad to section offset ─────────────────────────────────────────────
        cur = f.tell()
        if cur < sect_off:
            f.write(b"\x00" * (sect_off - cur))

        # ── .text section: real RET instruction + INT3 filler ────────────────
        f.write(b"\xc3")    # RETN — valid entry point
        written = f.tell()
        left    = size - written
        buf     = b"\xcc" * CHUNK   # INT3 — debugger breakpoint, standard filler
        while left > 0:
            block   = min(left, CHUNK)
            f.write(buf[:block])
            left    -= block
            written += block
            cb(written / size)


def gen_csv(path: str, size: int, cb):
    """
    Valid CSV: proper header row + data rows with realistic field names.
    Rows are generated until target size is reached.
    """
    header = "id,name,email,department,salary,start_date,active,notes\n"
    row_tmpl = '{id},User{id},user{id}@example.com,Engineering,{sal:.2f},2024-01-{day:02d},true,Test data row {id}\n'
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(header)
        written = len(header.encode())
        row_id  = 1
        while written < size:
            row = row_tmpl.format(
                id=row_id,
                sal=30000 + (row_id % 70000),
                day=(row_id % 28) + 1
            )
            f.write(row)
            written += len(row.encode())
            row_id  += 1
            if row_id % 5000 == 0:
                cb(written / size)


def gen_doc(path: str, size: int, cb):
    """
    Valid .docx (Office Open XML, ZIP-based) saved as .doc extension.
    Contains a proper word/document.xml with paragraph text filler,
    all required relationships and content types.
    Opens correctly in Microsoft Word and LibreOffice Writer.

    Note: .doc (legacy OLE2 binary) format requires the `olefile` library.
    This implementation uses .docx structure (the modern standard)
    which Word opens transparently regardless of extension.
    """
    # Build in-memory ZIP (docx structure)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:

        z.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml"  ContentType="application/xml"/>
  <Override PartName="/word/document.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""")

        z.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="word/document.xml"/>
</Relationships>""")

        z.writestr("word/_rels/document.xml.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>""")

        # Estimate how many paragraphs we need
        para_text = "This is a generated test document paragraph used for file size testing purposes. " * 10
        para_xml  = f'<w:p><w:r><w:t xml:space="preserve">{para_text}</w:t></w:r></w:p>\n'
        overhead  = 800     # rough byte count for XML wrapper
        repeats   = max(1, (size - overhead) // len(para_xml.encode()))

        doc_open  = ('<?xml version="1.0" encoding="UTF-8"?>'
                     '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                     '<w:body>')
        doc_close = '<w:sectPr/></w:body></w:document>'

        doc_xml   = doc_open + para_xml * repeats + doc_close
        z.writestr("word/document.xml", doc_xml)

    raw = buf.getvalue()
    cb(0.5)

    # If zip is smaller than target, pad by appending a ZIP comment
    # (ZIP comment is part of the End of Central Directory record)
    # We re-pack with a comment appended
    if len(raw) < size:
        pad_needed = size - len(raw) - 2  # -2 for comment length field
        if pad_needed > 0 and pad_needed <= 65535:
            # Replace the 2-byte comment length at the end of the EOCD
            raw = raw[:-2] + struct.pack("<H", pad_needed) + b"\x58" * pad_needed
        elif pad_needed > 65535:
            # Build a bigger document with more paragraphs
            extra_paras = (pad_needed // len(para_xml.encode())) + 1
            doc_xml     = doc_open + para_xml * (repeats + extra_paras) + doc_close
            buf2 = io.BytesIO()
            with zipfile.ZipFile(buf2, "w", zipfile.ZIP_DEFLATED) as z2:
                z2.writestr("[Content_Types].xml", z.namelist()[0] if False else
                    """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml"  ContentType="application/xml"/>
  <Override PartName="/word/document.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""")
                z2.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="word/document.xml"/>
</Relationships>""")
                z2.writestr("word/_rels/document.xml.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>""")
                z2.writestr("word/document.xml", doc_xml)
            raw = buf2.getvalue()

    with open(path, "wb") as f:
        f.write(raw)
        # If still short, pad with nulls (outside ZIP — harmless)
        if f.tell() < size:
            f.write(b"\x00" * (size - f.tell()))
    cb(1.0)


# ─── Generator dispatch ───────────────────────────────────────────────────────
GENERATORS = {
    "jpg":  gen_jpeg,
    "jpeg": gen_jpeg,
    "png":  gen_png,
    "mp4":  gen_mp4,
    "exe":  gen_exe,
    "csv":  gen_csv,
    "doc":  gen_doc,
}

# ─── GUI ──────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("File Generator — Upload Test Tool")
        self.configure(bg=BG)
        self.resizable(False, False)
        self._gen_thread = None
        self._cancel     = False
        self._build()
        # Center window
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build(self):
        self._apply_style()
        root = self

        # ── Header ──────────────────────────────────────────────────────────
        hdr = tk.Frame(root, bg=SF, pady=14)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⬡  File Generator", font=(FONT, 16, "bold"),
                 fg=BLUE, bg=SF).pack()
        tk.Label(hdr, text="Generate valid files for upload testing",
                 font=(FONT, 9), fg=MUTED, bg=SF).pack()

        # ── Main card ────────────────────────────────────────────────────────
        card = tk.Frame(root, bg=BG, padx=28, pady=20)
        card.pack(fill="both", expand=True)

        def row(label, col=0):
            tk.Label(card, text=label, font=(FONT, 10), fg=MUTED, bg=BG,
                     anchor="w").grid(row=col, column=0, sticky="w",
                                      pady=(10, 2), padx=(0, 16))

        # File type
        row("File Type", 0)
        self.ftype = tk.StringVar(value="jpg")
        types = ["jpg", "jpeg", "png", "mp4", "exe", "csv", "doc"]
        opt = ttk.Combobox(card, textvariable=self.ftype, values=types,
                           state="readonly", font=(FONT, 11), width=10)
        opt.grid(row=0, column=1, sticky="w", pady=(10, 2))
        opt.bind("<<ComboboxSelected>>", self._update_filename)

        # Size row (value + unit)
        row("File Size", 1)
        size_frame = tk.Frame(card, bg=BG)
        size_frame.grid(row=1, column=1, sticky="w", pady=(10, 2))
        self.size_val = tk.StringVar(value="10")
        size_entry = tk.Entry(size_frame, textvariable=self.size_val,
                              font=(FONT, 12, "bold"), width=8,
                              bg=SF, fg=TEXT, insertbackground=TEXT,
                              relief="flat", bd=6)
        size_entry.pack(side="left")
        size_entry.bind("<KeyRelease>", self._update_filename)

        self.size_unit = tk.StringVar(value="MB")
        for u in ["KB", "MB", "GB"]:
            rb = tk.Radiobutton(size_frame, text=u, variable=self.size_unit,
                                value=u, font=(FONT, 10), fg=MUTED, bg=BG,
                                selectcolor=BG, activebackground=BG,
                                activeforeground=BLUE,
                                command=self._update_filename)
            rb.pack(side="left", padx=(10, 0))

        # Output directory
        row("Save To", 2)
        dir_frame = tk.Frame(card, bg=BG)
        dir_frame.grid(row=2, column=1, sticky="ew", pady=(10, 2))
        self.out_dir = tk.StringVar(value=str(Path.home() / "Downloads"))
        dir_entry = tk.Entry(dir_frame, textvariable=self.out_dir,
                             font=(FONT, 10), width=32,
                             bg=SF, fg=TEXT, insertbackground=TEXT,
                             relief="flat", bd=6)
        dir_entry.pack(side="left", fill="x", expand=True)
        tk.Button(dir_frame, text="Browse", font=(FONT, 9),
                  bg=BD, fg=TEXT, relief="flat", bd=0, padx=8,
                  cursor="hand2",
                  command=self._browse).pack(side="left", padx=(6, 0))

        # Filename
        row("Filename", 3)
        self.filename = tk.StringVar(value="test_10mb.jpg")
        fn_entry = tk.Entry(card, textvariable=self.filename,
                            font=(FONT, 11), width=30,
                            bg=SF, fg=TEXT, insertbackground=TEXT,
                            relief="flat", bd=6)
        fn_entry.grid(row=3, column=1, sticky="w", pady=(10, 2))

        # ── Progress ─────────────────────────────────────────────────────────
        tk.Label(card, text="", bg=BG).grid(row=4, column=0, pady=6)
        self.progress = ttk.Progressbar(card, length=400, mode="determinate",
                                        style="Red.Horizontal.TProgressbar")
        self.progress.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        self.pct_label = tk.Label(card, text="", font=(FONT, 9),
                                  fg=MUTED, bg=BG)
        self.pct_label.grid(row=6, column=0, columnspan=2)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_frame = tk.Frame(card, bg=BG)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=(14, 0))

        self.gen_btn = tk.Button(btn_frame, text="⚡  Generate File",
                                 font=(FONT, 12, "bold"),
                                 bg=RED, fg="white", relief="flat", bd=0,
                                 padx=22, pady=10, cursor="hand2",
                                 command=self._start)
        self.gen_btn.pack(side="left", padx=(0, 10))

        self.cancel_btn = tk.Button(btn_frame, text="Cancel",
                                    font=(FONT, 10),
                                    bg=BD, fg=MUTED, relief="flat", bd=0,
                                    padx=14, pady=10, cursor="hand2",
                                    state="disabled",
                                    command=self._cancel_gen)
        self.cancel_btn.pack(side="left")

        # ── Log ───────────────────────────────────────────────────────────────
        tk.Label(card, text="Log", font=(FONT, 9), fg=MUTED, bg=BG,
                 anchor="w").grid(row=8, column=0, columnspan=2,
                                  sticky="w", pady=(18, 2))
        log_frame = tk.Frame(card, bg=SF, bd=1, relief="flat")
        log_frame.grid(row=9, column=0, columnspan=2, sticky="nsew")
        card.rowconfigure(9, weight=1)
        card.columnconfigure(1, weight=1)

        self.log = tk.Text(log_frame, height=9, width=56,
                           font=(FONT, 9), bg=SF, fg=TEXT,
                           insertbackground=TEXT, relief="flat",
                           state="disabled", wrap="word")
        sb = ttk.Scrollbar(log_frame, orient="vertical",
                           command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        self.log.pack(side="left", fill="both", expand=True, padx=8, pady=6)
        sb.pack(side="right", fill="y")

        # Tag colours for log
        self.log.tag_configure("ok",   foreground=GREEN)
        self.log.tag_configure("err",  foreground=RED)
        self.log.tag_configure("warn", foreground=YELLOW)
        self.log.tag_configure("info", foreground=BLUE)
        self.log.tag_configure("dim",  foreground=MUTED)

        # ── Footer ────────────────────────────────────────────────────────────
        tk.Label(root, text="For authorised upload testing only",
                 font=(FONT, 8), fg=MUTED, bg=BG, pady=6).pack()

        # Initial log
        self._log("Ready. Configure file type, size, and output path, then click Generate.", "dim")

    # ── Style ─────────────────────────────────────────────────────────────────
    def _apply_style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=TEXT, font=(FONT, 10))
        s.configure("TCombobox", fieldbackground=SF, background=SF,
                    foreground=TEXT, selectbackground=SF,
                    selectforeground=TEXT, arrowcolor=MUTED)
        s.map("TCombobox", fieldbackground=[("readonly", SF)],
              selectbackground=[("readonly", SF)],
              foreground=[("readonly", TEXT)])
        s.configure("TScrollbar", background=BD, troughcolor=SF,
                    arrowcolor=MUTED, borderwidth=0)
        s.configure("Red.Horizontal.TProgressbar",
                    troughcolor=SF, background=RED, borderwidth=0)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _log(self, msg: str, tag: str = ""):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{ts}] {msg}\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _update_filename(self, *_):
        try:
            val  = float(self.size_val.get() or "0")
            unit = self.size_unit.get()
            ext  = self.ftype.get()
            name = f"test_{int(val)}{unit.lower()}.{ext}"
            self.filename.set(name)
        except ValueError:
            pass

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self.out_dir.get())
        if d:
            self.out_dir.set(d)

    # ── Generation ────────────────────────────────────────────────────────────
    def _start(self):
        # Validate inputs
        try:
            val = float(self.size_val.get())
            if val <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid size", "Please enter a positive number for the file size.")
            return

        unit = self.size_unit.get()
        size = to_bytes(val, unit)
        ext  = self.ftype.get()
        fn   = self.filename.get().strip() or f"test.{ext}"
        out  = os.path.join(self.out_dir.get(), fn)

        if not os.path.isdir(self.out_dir.get()):
            messagebox.showerror("Invalid directory", f"Directory does not exist:\n{self.out_dir.get()}")
            return

        if os.path.exists(out):
            if not messagebox.askyesno("File exists", f"{fn} already exists. Overwrite?"):
                return

        self._cancel     = False
        self.progress["value"] = 0
        self.pct_label.config(text="")
        self.gen_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")

        self._log(f"Generating {fn}  ({human(size)})  →  {self.out_dir.get()}", "info")
        self._start_time = time.time()

        gen_fn = GENERATORS.get(ext)
        self._gen_thread = threading.Thread(
            target=self._run_gen,
            args=(gen_fn, out, size, ext),
            daemon=True
        )
        self._gen_thread.start()

    def _run_gen(self, gen_fn, out: str, size: int, ext: str):
        def cb(frac: float):
            if self._cancel:
                raise InterruptedError("Cancelled")
            pct = min(100, frac * 100)
            self.after(0, self._update_progress, pct)

        try:
            gen_fn(out, size, cb)
            elapsed  = time.time() - self._start_time
            actual   = os.path.getsize(out)
            speed    = actual / elapsed if elapsed > 0 else 0
            self.after(0, self._done, out, actual, elapsed, speed)
        except InterruptedError:
            try: os.remove(out)
            except: pass
            self.after(0, self._cancelled)
        except Exception as e:
            try: os.remove(out)
            except: pass
            self.after(0, self._error, str(e))

    def _update_progress(self, pct: float):
        self.progress["value"] = pct
        elapsed = time.time() - self._start_time
        self.pct_label.config(
            text=f"{pct:.1f}%  —  {elapsed:.1f}s elapsed"
        )

    def _done(self, out: str, actual: int, elapsed: float, speed: float):
        self.progress["value"] = 100
        self.pct_label.config(text=f"100%  —  {elapsed:.1f}s")
        self._log(f"Done  {human(actual)}  written in {elapsed:.1f}s  ({human(int(speed))}/s)", "ok")
        self._log(f"Saved → {out}", "ok")
        self._reset_buttons()

    def _cancelled(self):
        self.progress["value"] = 0
        self.pct_label.config(text="Cancelled")
        self._log("Generation cancelled.", "warn")
        self._reset_buttons()

    def _error(self, msg: str):
        self.progress["value"] = 0
        self.pct_label.config(text="Error")
        self._log(f"Error: {msg}", "err")
        self._reset_buttons()
        messagebox.showerror("Generation failed", msg)

    def _cancel_gen(self):
        self._cancel = True

    def _reset_buttons(self):
        self.gen_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")


if __name__ == "__main__":
    app = App()
    app.mainloop()
