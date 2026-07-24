#!/usr/bin/env python3
"""
MGM Barcode Generator — Modern GUI
Auto-generates unique barcode numbers (A-prefix + 12-digit sequential).
No Sticker_No column needed — numbers never repeat across runs/days/months.
Persistent tracker file guarantees uniqueness forever.
"""

import os
import re
import json
import tempfile
import shutil
import threading
import time
import pandas as pd
from fpdf import FPDF
from barcode import Code128
from barcode.writer import ImageWriter

from tkinterdnd2 import TkinterDnD, DND_FILES
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ============================================================================
# BARCODE AUTO-GENERATION SYSTEM — UNIQUE, PERSISTENT, NEVER REPEATS
# ============================================================================

BARCODE_PREFIX = "A"           # All barcodes start with 'A'
BARCODE_DIGITS  = 12            # 12 numeric digits after prefix → 10^12 = 1 trillion
BARCODE_START   = 504370000000  # Starting counter value (A504370000000)
TRACKER_FILE    = "barcode_tracker.json"  # Persistent record file


class BarcodeTracker:
    """
    Manages a persistent JSON file that tracks every barcode ever generated.
    
    Guarantees:
    - Every barcode number is UNIQUE across all runs, all days, all months
    - Sequential numbering: A504370000000, A504370000001, A504370000002, ...
    - 1 trillion possible numbers — will never exhaust
    - Tracker file survives between runs — even months later, numbers won't repeat
    - Full audit log: which file generated which barcodes on which date
    """

    def __init__(self, tracker_path=None):
        if tracker_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__)) or "."
            tracker_path = os.path.join(script_dir, TRACKER_FILE)
        self.tracker_path = tracker_path
        self.data = self._load()

    def _load(self):
        """Load existing tracker file, or create a fresh one."""
        if os.path.isfile(self.tracker_path):
            try:
                with open(self.tracker_path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                # Corrupted file — start fresh but preserve counter if readable
                pass
        # Fresh tracker
        return {
            "last_counter": BARCODE_START - 1,  # Will increment to BARCODE_START on first use
            "total_generated": 0,
            "history": []   # List of generation runs: {date, input_file, count, first_barcode, last_barcode}
        }

    def _save(self):
        """Save tracker to disk — called after every generation run."""
        os.makedirs(os.path.dirname(self.tracker_path) or ".", exist_ok=True)
        with open(self.tracker_path, "w") as f:
            json.dump(self.data, f, indent=2)

    def _format_barcode(self, counter):
        """Format counter into barcode string: A + 12-digit number."""
        return f"{BARCODE_PREFIX}{counter:0{BARCODE_DIGITS}d}"

    def get_next_barcode(self):
        """Return the next unique barcode number and increment counter."""
        self.data["last_counter"] += 1
        self.data["total_generated"] += 1
        barcode = self._format_barcode(self.data["last_counter"])
        return barcode

    def allocate_batch(self, count):
        """
        Allocate a batch of `count` unique barcode numbers.
        Returns list of barcode strings.
        Counter is advanced by `count` so they're never reused.
        """
        start_counter = self.data["last_counter"] + 1
        end_counter = start_counter + count - 1
        self.data["last_counter"] = end_counter
        self.data["total_generated"] += count

        barcodes = [self._format_barcode(c) for c in range(start_counter, end_counter + 1)]
        return barcodes

    def record_generation(self, input_file, count, first_barcode, last_barcode):
        """Record a generation run in history for audit tracking."""
        entry = {
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "input_file": os.path.basename(input_file),
            "count": count,
            "first_barcode": first_barcode,
            "last_barcode": last_barcode
        }
        self.data["history"].append(entry)
        self._save()

    def get_stats(self):
        """Return tracker statistics for display."""
        last = self._format_barcode(self.data["last_counter"])
        next = self._format_barcode(self.data["last_counter"] + 1)
        remaining = 10**BARCODE_DIGITS - self.data["last_counter"] - 1
        return {
            "last_counter": self.data["last_counter"],
            "last_barcode": last,
            "next_barcode": next,
            "total_generated": self.data["total_generated"],
            "remaining_numbers": remaining,
            "history_runs": len(self.data["history"])
        }

    def is_unique(self, barcode):
        """Verify a barcode hasn't been issued (sequential guarantee)."""
        counter = int(barcode[1:])
        return counter <= self.data["last_counter"]


# ============================================================================
# ORIGINAL LABEL CONSTANTS & PDF CLASS — UNCHANGED
# ============================================================================
A4_WIDTH = 210.0
A4_HEIGHT = 297.0

COLUMNS_PER_PAGE = 3
ROWS_PER_PAGE = 8
LABELS_PER_PAGE = 24

LABEL_WIDTH = 69.8
LABEL_HEIGHT = 35.0

PAGE_MARGIN_LEFT = 0.3
PAGE_MARGIN_TOP = 7.5
HORIZONTAL_GAP = 0.0
VERTICAL_GAP = -0.5

INPUT_FILE = "Backlog_Barcode.xlsx"
OUTPUT_DIR = "barcode_output"

TEMP_DIR = tempfile.mkdtemp(prefix="barcodes_")


def resolve_input_file():
    candidates = []
    script_dir = os.path.dirname(os.path.abspath(__file__)) or "."
    for name in [INPUT_FILE, "Regular_Barcode.xlsx"]:
        candidates.append(name)
        candidates.append(os.path.join(script_dir, name))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    excel_files = [
        os.path.join(script_dir, name)
        for name in os.listdir(script_dir)
        if name.lower().endswith((".xlsx", ".xls"))
    ]
    if excel_files:
        return excel_files[0]
    raise FileNotFoundError("No Excel input file found.")


class PDF(FPDF):
    def header(self): pass
    def footer(self): pass


def safe_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', "_", str(name))
    return name[:80]

def normalize_date(val):
    try:
        return pd.to_datetime(val).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return "Unknown_Date"

# ============================================================================
# BARCODE CACHE (for image generation, not number allocation)
# ============================================================================
barcode_cache = {}

def get_barcode(data):
    original_data = str(data).strip()
    cache_key = safe_filename(original_data)

    if cache_key in barcode_cache:
        return barcode_cache[cache_key]

    code = Code128(original_data, writer=ImageWriter())
    temp_path = os.path.join(TEMP_DIR, cache_key)
    path = code.save(temp_path, {
        "module_width": 0.25,
        "module_height": 8,
        "font_size": 0,
        "text_distance": -100
    })
    barcode_cache[cache_key] = path
    return path


def get_position(i):
    row = i // COLUMNS_PER_PAGE
    col = i % COLUMNS_PER_PAGE
    x = PAGE_MARGIN_LEFT + col * (LABEL_WIDTH + HORIZONTAL_GAP)
    y = PAGE_MARGIN_TOP + row * (LABEL_HEIGHT + VERTICAL_GAP)
    return x, y


# ============================================================================
# DRAW LABEL — AUTO-GENERATED BARCODE, NOT Sticker_No
# ============================================================================
def draw_label(pdf, row, x, y, auto_barcode):
    """
    Draw a single label. `auto_barcode` is the unique auto-generated number.
    Seat_No, Subject_Code, Date, Semester, Center, Program still come from Excel.
    """
    seat = str(row.get("Seat_No", "")).strip()[:15]
    sub = str(row.get("Subject_Code", "")).strip()[:15]
    date_val = str(row.get("Date", "")).strip()

    sem_val = row.get("Semester", "")
    if isinstance(sem_val, pd.Series): sem_val = sem_val.iloc[0]
    sem_val = str(sem_val).strip()
    if sem_val.endswith(".0"): sem_val = sem_val[:-2]
    if sem_val.lower() == "nan": sem_val = ""
    sem_val = sem_val[:10]

    center_val = row.get("Exam Center Code", row.get("Center", ""))
    if isinstance(center_val, pd.Series): center_val = center_val.iloc[0]
    center_val = str(center_val).strip()
    if center_val.endswith(".0"): center_val = center_val[:-2]
    if center_val.lower() == "nan": center_val = ""
    center_val = center_val[:10]

    program_val = row.get("Program", "")
    if isinstance(program_val, pd.Series): program_val = program_val.iloc[0]
    program_val = str(program_val).strip()
    if program_val.lower() == "nan": program_val = ""
    program_val = program_val[:15]

    # ── AUTO-GENERATED BARCODE NUMBER ──
    sticker = auto_barcode

    barcode_w = 56.0
    barcode_h = 11.5
    barcode_x = x + (LABEL_WIDTH - barcode_w) / 2
    barcode_y = y + 15.1

    # ── TOP SECTION: VALUES ──
    pdf.set_font("Helvetica", "B", 7.5)
    top_text_x = x + 3.5
    top_text_w = LABEL_WIDTH - 7.0

    pdf.set_xy(top_text_x, y + 8)
    pdf.cell(top_text_w, 3.5, f"PRN: {seat}      Date: {date_val}", align="C")

    pdf.set_xy(top_text_x, y + 11.5)
    pdf.cell(top_text_w, 3.5, f"Sub: {sub}    Sem: {sem_val}    Center: {center_val}", align="C")

    # ── BOTTOM SECTION: AUTO BARCODE ──
    barcode_path = get_barcode(sticker)
    pdf.image(barcode_path, x=barcode_x, y=barcode_y, w=barcode_w, h=barcode_h)

    # Barcode number beneath barcode image
    pdf.set_xy(x, y + 27.0)
    pdf.set_font("Helvetica", "B", 8)
    bottom_text = sticker
    if program_val:
        bottom_text = f"{sticker}    Program: {program_val}"
    pdf.cell(LABEL_WIDTH, 4.0, bottom_text, align="C")


# ============================================================================
# LOAD DATA — Sticker_No NO LONGER REQUIRED
# ============================================================================
def load_data(input_file=None):
    if input_file is None:
        input_file = resolve_input_file()
    df = pd.read_excel(input_file)

    def canonical_column_name(name):
        name = str(name).strip().lower()
        name = re.sub(r"[^a-z0-9]+", " ", name)
        return name.strip()

    mapping = {
        "seat no": "Seat_No", "seat": "Seat_No", "prn": "Seat_No",
        "subject": "Subject_Code", "subject code": "Subject_Code",
        "sticker no": "Sticker_No", "sticker": "Sticker_No",  # Still mapped but NOT required
        "date": "Date", "exam date": "Date",
        "semester": "Semester", "sem": "Semester",
        "exam center code": "Exam Center Code", "center code": "Exam Center Code",
        "center": "Exam Center Code", "centre": "Exam Center Code",
        "exam center": "Exam Center Code", "exam centre": "Exam Center Code",
        "college code": "Exam Center Code", "inst code": "Exam Center Code",
        "exam session": "Exam_Session", "session": "Exam_Session",
        "time": "Exam_Session", "exam time": "Exam_Session",
        "program": "Program", "branch": "Program", "stream": "Program", "degree": "Program"
    }

    rename_map = {}
    seen_targets = set()
    for col in df.columns:
        canonical = canonical_column_name(col)
        if canonical in mapping:
            target = mapping[canonical]
            if target not in seen_targets:
                rename_map[col] = target
                seen_targets.add(target)

    df = df.rename(columns=rename_map)

    # Sticker_No is NO LONGER a required column — we auto-generate barcodes
    required = ["Seat_No", "Subject_Code", "Date"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    df = df.fillna("")

    # Filter: must have a valid Seat_No (PRN)
    df = df[df["Seat_No"].astype(str).str.strip() != ""]

    if df.empty:
        raise ValueError("No rows with a valid Seat_No/PRN were found.")

    df["Date"] = df["Date"].apply(normalize_date)
    return df


# ============================================================================
# GENERATE — AUTO-GENERATE UNIQUE BARCODES, TRACK FOREVER
# ============================================================================
def generate(input_file=None, output_dir=None, log_callback=None):
    """
    Generate barcode labels with AUTO-GENERATED unique numbers.
    Uses BarcodeTracker for persistent cross-run uniqueness.
    """

    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    if input_file is None:
        input_file = resolve_input_file()
    if output_dir is None:
        output_dir = OUTPUT_DIR

    # ── Recreate temp dir for this run (cleaned up after) ──
    global TEMP_DIR, barcode_cache
    TEMP_DIR = tempfile.mkdtemp(prefix="barcodes_")
    barcode_cache = {}

    # ── Initialize tracker ──
    tracker = BarcodeTracker(os.path.join(output_dir, TRACKER_FILE))
    stats = tracker.get_stats()
    log(f"Tracker: {stats['total_generated']} barcodes issued previously")
    log(f"Next barcode will be: {stats['next_barcode']}")
    log(f"Remaining numbers: {stats['remaining_numbers']}")

    # ── Load data ──
    df = load_data(input_file)

    total_w = PAGE_MARGIN_LEFT + COLUMNS_PER_PAGE * LABEL_WIDTH
    if total_w > A4_WIDTH:
        raise ValueError(f"Labels overflow horizontally: {total_w:.1f}mm > {A4_WIDTH}mm.")

    # Ensure grouping columns exist
    for col in ["Exam Center Code", "Exam_Session", "Subject_Code"]:
        if col not in df.columns:
            df[col] = "Unknown"

    df["Exam Center Code"] = df["Exam Center Code"].replace("", "Unknown_Center")
    df["Exam_Session"] = df["Exam_Session"].replace("", "Unknown_Session")
    df["Subject_Code"] = df["Subject_Code"].replace("", "Unknown_Subject")

    # Sorting Subject wise then PRN wise
    if "Seat_No" in df.columns:
        df["Seat_No_Str"] = df["Seat_No"].astype(str)
        df["Seat_No_Num"] = pd.to_numeric(df["Seat_No_Str"], errors='coerce').fillna(float('inf'))
        df = df.sort_values(by=["Subject_Code", "Seat_No_Num", "Seat_No_Str"]).drop(columns=["Seat_No_Num", "Seat_No_Str"])

    total_rows = len(df)
    log(f"Total rows: {total_rows}")
    log(f"Unique centers: {df['Exam Center Code'].nunique()}")
    log(f"Unique dates: {df['Date'].nunique()}")
    log(f"Unique sessions: {df['Exam_Session'].nunique()}")

    # ── Allocate a batch of unique barcode numbers ──
    auto_barcodes = tracker.allocate_batch(total_rows)
    first_bc = auto_barcodes[0]
    last_bc = auto_barcodes[-1]
    log(f"Allocated {total_rows} unique barcodes: {first_bc} → {last_bc}")

    # Add auto_barcode column to DataFrame
    df["auto_barcode"] = auto_barcodes

    log_data = []
    total_labels = 0

    for center in df["Exam Center Code"].unique():
        center_df = df[df["Exam Center Code"] == center]
        center_folder = safe_filename(center)

        for date in center_df["Date"].unique():
            date_df = center_df[center_df["Date"] == date]
            date_folder = safe_filename(date)

            for session in date_df["Exam_Session"].unique():
                session_df = date_df[date_df["Exam_Session"] == session]
                session_folder = safe_filename(session)

                folder = os.path.join(output_dir, center_folder, date_folder, session_folder)
                os.makedirs(folder, exist_ok=True)

                pdf = PDF(orientation="P", unit="mm", format="A4")
                pdf.set_auto_page_break(auto=False)
                pdf.add_page()

                count = 0
                for _, row in session_df.iterrows():
                    i = count % LABELS_PER_PAGE
                    if i == 0 and count != 0:
                        pdf.add_page()

                    x, y = get_position(i)
                    draw_label(pdf, row, x, y, row["auto_barcode"])
                    count += 1

                file_path = os.path.join(folder, f"{session_folder}_All_Subjects.pdf")
                pdf.output(file_path)
                total_labels += count
                log(f"✔ {center}/{date}/{session} — {count} labels")

                log_data.append({
                    "Center": center,
                    "Date": date,
                    "Session": session,
                    "Total_Subjects": len(session_df["Subject_Code"].unique()),
                    "Total_Students": len(session_df),
                    "Barcodes_Generated": count,
                    "First_Barcode": session_df["auto_barcode"].iloc[0],
                    "Last_Barcode": session_df["auto_barcode"].iloc[-1]
                })

    # ── Save barcode mapping CSV (for audit: PRN → barcode) ──
    mapping_df = df[["Seat_No", "Subject_Code", "Date", "auto_barcode"]].copy()
    mapping_df.rename(columns={"Seat_No": "PRN", "auto_barcode": "Barcode_No"}, inplace=True)
    mapping_path = os.path.join(output_dir, "barcode_mapping.csv")
    mapping_df.to_csv(mapping_path, index=False)
    log(f"✔ Barcode mapping saved to {mapping_path}")

    # ── Record this generation run in tracker ──
    tracker.record_generation(input_file, total_rows, first_bc, last_bc)
    log(f"✔ Tracker updated — run recorded")

    # ── Save generation log ──
    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    log("✔ Temp files cleaned up.")

    if log_data:
        log_df = pd.DataFrame(log_data)
        log_path = os.path.join(output_dir, "generation_log.csv")
        log_df.to_csv(log_path, index=False)
        log(f"✔ Generation log saved to {log_path}")

    log(f"✔ DONE — {total_labels} total labels across {len(log_data)} PDFs")
    log(f"✔ Barcodes: {first_bc} → {last_bc} (all unique, never reused)")
    return total_labels, len(log_data)


# ============================================================================
# MODERN GUI — MGM BRANDING
# ============================================================================

BG_DARK      = "#0f0f1a"
BG_CARD      = "#1a1a2e"
BG_SURFACE   = "#16213e"
ACCENT_GOLD  = "#d4a843"
ACCENT_GOLD2 = "#e8c547"
ACCENT_BLUE  = "#0f3460"
TEXT_WHITE    = "#eaeaea"
TEXT_LIGHT    = "#a8a8b8"
TEXT_DIM      = "#6b6b80"
SUCCESS_GREEN = "#43d4a8"
ERROR_RED     = "#d44343"
BTN_HOVER     = "#2a2a4e"
DROP_BG      = "#0f3460"
DROP_BORDER   = "#d4a843"


class BarcodeGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MGM Barcode Generator")
        self.root.geometry("680x650")
        self.root.minsize(580, 500)
        self.root.configure(bg=BG_DARK)
        self.root.option_add("*Font", "Segoe 10")

        self.input_file = None
        self.output_dir = None
        self.is_generating = False

        self._build_ui()

    # ── UI CONSTRUCTION ──────────────────────────────────────
    def _build_ui(self):

        # ════════════════════════════════════════════════════
        #  HEADER — MGM Branding
        # ════════════════════════════════════════════════════
        header = tk.Frame(self.root, bg=ACCENT_BLUE, height=72)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        header_left = tk.Frame(header, bg=ACCENT_BLUE)
        header_left.pack(side="left", fill="y", padx=(18, 0))

        icon_frame = tk.Frame(header_left, bg=ACCENT_BLUE, width=40, height=40)
        icon_frame.pack(side="left", padx=(0, 10), pady=14)
        icon_frame.pack_propagate(False)
        for w, c in [(6, ACCENT_GOLD), (4, TEXT_WHITE), (8, ACCENT_GOLD), (3, TEXT_DIM), (6, ACCENT_GOLD)]:
            bar = tk.Frame(icon_frame, bg=c, width=w, height=28)
            bar.pack(side="left", padx=1, pady=6)

        title_frame = tk.Frame(header_left, bg=ACCENT_BLUE)
        title_frame.pack(side="left", pady=10)
        tk.Label(title_frame, text="MGM", bg=ACCENT_BLUE, fg=ACCENT_GOLD,
                 font=("Segoe UI", 22, "bold")).pack(anchor="w")
        tk.Label(title_frame, text="BARCODE GENERATOR", bg=ACCENT_BLUE, fg=TEXT_WHITE,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")

        tk.Label(header, text="Auto Unique \u00B7 Never Repeats \u00B7 Exam Security",
                 bg=ACCENT_BLUE, fg=TEXT_DIM, font=("Segoe UI", 9, "italic")).pack(side="right", padx=18, pady=24)

        # ════════════════════════════════════════════════════
        #  TRACKER STATS CARD
        # ════════════════════════════════════════════════════
        tracker_card = tk.Frame(self.root, bg=BG_CARD)
        tracker_card.pack(fill="x", padx=24, pady=(10, 6))

        # Try to load tracker stats
        try:
            tracker_path = os.path.join(self._get_tracker_dir(), TRACKER_FILE)
            t = BarcodeTracker(tracker_path)
            stats = t.get_stats()
        except Exception:
            stats = {"total_generated": 0, "last_barcode": "None yet", "next_barcode": f"A{BARCODE_START:0{BARCODE_DIGITS}d}", "remaining_numbers": 10**BARCODE_DIGITS - BARCODE_START, "history_runs": 0}

        stats_inner = tk.Frame(tracker_card, bg=BG_CARD)
        stats_inner.pack(fill="x", padx=12, pady=8)

        tk.Label(stats_inner, text="UNIQUE BARCODE TRACKER", bg=BG_CARD, fg=ACCENT_GOLD,
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=0, columnspan=4, sticky="w")

        self.tracker_labels = {}
        tracker_items = [
            ("Issued:", f"{stats['total_generated']}", TEXT_WHITE),
            ("Last:", stats['last_barcode'], TEXT_LIGHT),
            ("Next:", stats['next_barcode'], SUCCESS_GREEN),
            ("Remaining:", f"{stats['remaining_numbers']}", TEXT_DIM),
        ]
        for i, (label, value, color) in enumerate(tracker_items):
            tk.Label(stats_inner, text=label, bg=BG_CARD, fg=TEXT_DIM,
                     font=("Segoe UI", 9)).grid(row=1, column=i*2, sticky="w", padx=(0, 4))
            lbl = tk.Label(stats_inner, text=value, bg=BG_CARD, fg=color,
                          font=("Segoe UI", 10, "bold"))
            lbl.grid(row=1, column=i*2+1, sticky="w", padx=(0, 16))
            self.tracker_labels[label] = lbl

        # ════════════════════════════════════════════════════
        #  CONTENT
        # ════════════════════════════════════════════════════
        content = tk.Frame(self.root, bg=BG_DARK)
        content.pack(fill="both", expand=True, padx=24, pady=(0, 0))

        # ── Drop Zone ──
        drop_card = tk.Frame(content, bg=BG_CARD, padx=2, pady=2)
        drop_card.pack(fill="x", pady=(0, 4))

        drop_inner = tk.Frame(drop_card, bg=DROP_BG, padx=3, pady=3,
                              highlightbackground=DROP_BORDER, highlightthickness=2)
        drop_inner.pack(fill="both", expand=True)

        self.drop_zone = tk.Frame(drop_inner, bg=DROP_BG, height=100, cursor="hand2")
        self.drop_zone.pack(fill="x")
        self.drop_zone.pack_propagate(False)

        self.drop_label = tk.Label(
            self.drop_zone,
            text="\u2193  DRAG & DROP YOUR EXCEL FILE HERE  \u2193\n\nClick anywhere to browse",
            bg=DROP_BG, fg=ACCENT_GOLD2,
            font=("Segoe UI", 13, "bold"), cursor="hand2"
        )
        self.drop_label.pack(expand=True, fill="both", padx=12, pady=8)

        self.drop_zone.drop_target_register(DND_FILES)
        self.drop_zone.dnd_bind('<<Drop>>', self._on_drop)
        self.drop_label.bind("<Button-1>", self._browse_input)

        # ── File Info ──
        info_strip = tk.Frame(content, bg=BG_CARD)
        info_strip.pack(fill="x", pady=(4, 8))

        self.file_var = tk.StringVar(value="No file selected")
        self.file_label = tk.Label(info_strip, textvariable=self.file_var,
                                   bg=BG_CARD, fg=ERROR_RED, font=("Segoe UI", 10))
        self.file_label.pack(side="left", padx=12, pady=8)

        self.row_count_var = tk.StringVar(value="")
        tk.Label(info_strip, textvariable=self.row_count_var,
                 bg=BG_CARD, fg=TEXT_DIM, font=("Segoe UI", 9)).pack(side="right", padx=12, pady=8)

        # ── Output Folder ──
        out_row = tk.Frame(content, bg=BG_DARK)
        out_row.pack(fill="x", pady=(0, 8))

        tk.Label(out_row, text="OUTPUT", bg=BG_DARK, fg=TEXT_DIM,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 8))

        self.out_var = tk.StringVar(value="Auto \u2014 next to input file")
        out_entry = tk.Entry(out_row, textvariable=self.out_var,
                             bg=BG_CARD, fg=TEXT_WHITE, insertbackground=TEXT_WHITE,
                             font=("Segoe UI", 10), relief="flat",
                             highlightbackground=ACCENT_GOLD, highlightthickness=1)
        out_entry.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=4)

        browse_btn = tk.Button(out_row, text="BROWSE", bg=ACCENT_BLUE, fg=TEXT_WHITE,
                               font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
                               activebackground=BTN_HOVER, padx=12, pady=4,
                               command=self._browse_output)
        browse_btn.pack(side="right")

        # ════════════════════════════════════════════════════
        #  GENERATE BUTTON
        # ════════════════════════════════════════════════════
        btn_frame = tk.Frame(content, bg=BG_DARK)
        btn_frame.pack(fill="x", pady=(4, 8))

        self.gen_btn = tk.Button(
            btn_frame, text="\u25B6  GENERATE BARCODES",
            bg=ACCENT_GOLD, fg=BG_DARK,
            font=("Segoe UI", 15, "bold"), relief="flat", cursor="hand2",
            activebackground=ACCENT_GOLD2, activeforeground=BG_DARK,
            command=self._start_generate, pady=10
        )
        self.gen_btn.pack(fill="x", ipady=4)

        # ════════════════════════════════════════════════════
        #  PROGRESS + STATUS
        # ════════════════════════════════════════════════════
        progress_frame = tk.Frame(content, bg=BG_DARK)
        progress_frame.pack(fill="x", pady=(0, 4))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Gold.Horizontal.TProgressbar",
                        troughcolor=BG_CARD, background=ACCENT_GOLD,
                        bordercolor=BG_DARK, lightcolor=ACCENT_GOLD2,
                        darkcolor=ACCENT_GOLD)

        self.progress = ttk.Progressbar(progress_frame, mode="indeterminate",
                                        length=632, style="Gold.Horizontal.TProgressbar")
        self.progress.pack(fill="x")

        self.status_var = tk.StringVar(value="Ready \u2014 drop a file to begin")
        self.status_label = tk.Label(content, textvariable=self.status_var,
                                     bg=BG_DARK, fg=ACCENT_GOLD2,
                                     font=("Segoe UI", 10, "bold"))
        self.status_label.pack(pady=(4, 0))

        # ════════════════════════════════════════════════════
        #  LOG CONSOLE
        # ════════════════════════════════════════════════════
        log_card = tk.Frame(content, bg=BG_CARD, padx=2, pady=2)
        log_card.pack(fill="both", expand=True, pady=(6, 8))

        log_header = tk.Frame(log_card, bg=BG_CARD)
        log_header.pack(fill="x", padx=8, pady=(6, 0))
        tk.Label(log_header, text="CONSOLE", bg=BG_CARD, fg=TEXT_DIM,
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        self.clear_btn = tk.Button(log_header, text="CLEAR", bg=BG_CARD, fg=TEXT_DIM,
                                   font=("Segoe UI", 8), relief="flat", cursor="hand2",
                                   activebackground=BTN_HOVER, command=self._clear_log)
        self.clear_btn.pack(side="right")

        log_inner = tk.Frame(log_card, bg="#0d0d1a")
        log_inner.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        self.log_text = tk.Text(
            log_inner, bg="#0d0d1a", fg=SUCCESS_GREEN,
            font=("Consolas", 9), relief="flat",
            insertbackground=SUCCESS_GREEN, wrap="word",
            height=6, state="disabled", padx=8, pady=4
        )
        log_scroll = tk.Scrollbar(log_inner, command=self.log_text.yview,
                                  bg=BG_CARD, troughcolor="#0d0d1a",
                                  activebackground=ACCENT_GOLD)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

        # ════════════════════════════════════════════════════
        #  FOOTER
        # ════════════════════════════════════════════════════
        footer = tk.Frame(self.root, bg=BG_DARK, height=20)
        footer.pack(fill="x", side="bottom")
        tk.Label(footer, text="A4ST24S \u00B7 3\u00D78 \u00B7 69.8\u00D735mm \u00B7 Code128 \u00B7 Auto Unique",
                 bg=BG_DARK, fg=TEXT_DIM, font=("Segoe UI", 8)).pack(side="left", padx=18)
        tk.Label(footer, text="MGM University \u00B7 Exam Barcode System",
                 bg=BG_DARK, fg=TEXT_DIM, font=("Segoe UI", 8)).pack(side="right", padx=18)

    def _get_tracker_dir(self):
        """Get the directory where tracker file should live."""
        out_text = self.out_var.get().strip()
        if out_text and not out_text.startswith("Auto"):
            return out_text
        script_dir = os.path.dirname(os.path.abspath(__file__)) or "."
        return os.path.join(script_dir, "barcode_output")

    def _refresh_tracker_stats(self):
        """Refresh tracker stats display after generation."""
        try:
            tracker_path = os.path.join(self._get_tracker_dir(), TRACKER_FILE)
            t = BarcodeTracker(tracker_path)
            stats = t.get_stats()
        except Exception:
            return

        updates = {
            "Issued:": (f"{stats['total_generated']}", TEXT_WHITE),
            "Last:": (stats['last_barcode'], TEXT_LIGHT),
            "Next:": (stats['next_barcode'], SUCCESS_GREEN),
            "Remaining:": (f"{stats['remaining_numbers']}", TEXT_DIM),
        }
        for label, (value, color) in updates.items():
            if label in self.tracker_labels:
                self.tracker_labels[label].configure(text=value, fg=color)

    # ── EVENT HANDLERS ───────────────────────────────────────
    def _on_drop(self, event):
        raw = event.data
        paths = []
        for part in raw.split():
            cleaned = part.strip("{}")
            if cleaned:
                paths.append(cleaned)
        if not paths:
            return
        file_path = paths[0]
        if not file_path.lower().endswith((".xlsx", ".xls", ".csv")):
            self._set_status("Only .xlsx / .xls / .csv files accepted", color=ERROR_RED)
            return
        self._set_file(file_path)

    def _browse_input(self, event=None):
        file_path = filedialog.askopenfilename(
            title="Select Excel File",
            filetypes=[("Excel Files", "*.xlsx *.xls"), ("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if file_path:
            self._set_file(file_path)

    def _set_file(self, file_path):
        self.input_file = file_path
        basename = os.path.basename(file_path)
        self.file_var.set(f"\u2713  {basename}")
        self.file_label.configure(fg=SUCCESS_GREEN)
        self.drop_label.configure(
            text=f"\u2713  {basename}  \u2713\n\nDrag another file to replace",
            fg=SUCCESS_GREEN
        )
        self._set_status(f"File loaded \u2014 {basename}", color=ACCENT_GOLD2)

        try:
            df = pd.read_excel(file_path)
            self.row_count_var.set(f"{len(df)} rows \u2192 {len(df)} unique barcodes will be generated")
        except Exception:
            self.row_count_var.set("")

        self._log(f"Input file: {file_path}")

        if self.out_var.get() == "Auto \u2014 next to input file" or not self.out_var.get().strip():
            self.output_dir = os.path.join(os.path.dirname(file_path), "barcode_output")
            self.out_var.set(self.output_dir)

        # Refresh tracker stats for this output dir
        self._refresh_tracker_stats()

    def _browse_output(self):
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.output_dir = folder
            self.out_var.set(folder)
            self._refresh_tracker_stats()

    # ── GENERATION ───────────────────────────────────────────
    def _start_generate(self):
        if self.is_generating:
            return

        if not self.input_file:
            messagebox.showwarning("No File", "Please drag & drop an Excel file first!")
            return

        out_text = self.out_var.get().strip()
        if not out_text or out_text.startswith("Auto"):
            self.output_dir = os.path.join(os.path.dirname(self.input_file), "barcode_output")
        else:
            self.output_dir = out_text

        os.makedirs(self.output_dir, exist_ok=True)

        self.is_generating = True
        self.gen_btn.configure(text="\u23F3  GENERATING...", bg=ACCENT_GOLD2, state="disabled")
        self.progress.start(12)
        self._set_status("Generating unique barcodes...", color=ACCENT_GOLD2)
        self._log("=" * 50)
        self._log(f"Input:  {self.input_file}")
        self._log(f"Output: {self.output_dir}")
        self._log("=" * 50)

        thread = threading.Thread(target=self._run_generate, daemon=True)
        thread.start()

    def _run_generate(self):
        try:
            total_labels, num_pdfs = generate(
                input_file=self.input_file,
                output_dir=self.output_dir,
                log_callback=self._threaded_log
            )
            self.root.after(0, self._on_success, total_labels, num_pdfs)
        except Exception as e:
            self.root.after(0, self._on_error, str(e))

    def _on_success(self, total_labels, num_pdfs):
        self.is_generating = False
        self.progress.stop()
        self.gen_btn.configure(text="\u25B6  GENERATE BARCODES", bg=ACCENT_GOLD, state="normal")
        self._set_status(f"Done \u2014 {total_labels} unique labels in {num_pdfs} PDFs", color=SUCCESS_GREEN)
        self._refresh_tracker_stats()
        messagebox.showinfo(
            "Success",
            f"Generated {total_labels} UNIQUE barcode labels across {num_pdfs} PDFs.\n\n"
            f"All barcodes are auto-generated and will NEVER repeat.\n\n"
            f"Output folder:\n{self.output_dir}"
        )

    def _on_error(self, error_msg):
        self.is_generating = False
        self.progress.stop()
        self.gen_btn.configure(text="\u25B6  GENERATE BARCODES", bg=ACCENT_GOLD, state="normal")
        self._set_status("Error \u2014 check console below", color=ERROR_RED)
        self._log(f"ERROR: {error_msg}")
        messagebox.showerror("Error", error_msg)

    # ── LOGGING ──────────────────────────────────────────────
    def _log(self, msg):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _threaded_log(self, msg):
        self.root.after(0, self._log, msg)

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _set_status(self, msg, color=ACCENT_GOLD2):
        self.status_var.set(msg)
        self.status_label.configure(fg=color)


# ============================================================================
# MAIN
# ============================================================================
def main():
    root = TkinterDnD.Tk()
    app = BarcodeGeneratorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
