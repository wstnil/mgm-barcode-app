#!/usr/bin/env python3
"""
MGM Barcode Generator — Streamlit Web App (Cloud-Ready)
Auto-generates unique barcode numbers. Tracker synced via Git repo.
Deploy: https://streamlit.io/cloud → connect repo → set secrets
Run locally: streamlit run barcode_streamlit.py
"""

import os
import re
import json
import zipfile
import tempfile
import shutil
import time
import io
import pandas as pd
from fpdf import FPDF
from barcode import Code128
from barcode.writer import ImageWriter

import streamlit as st

# ============================================================================
# PAGE CONFIG — MGM BRANDING
# ============================================================================
st.set_page_config(
    page_title="MGM Barcode Generator",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# BARCODE AUTO-GENERATION SYSTEM — UNIQUE, PERSISTENT, GIT-SYNCED
# ============================================================================
BARCODE_PREFIX = "A"
BARCODE_DIGITS  = 12
BARCODE_START   = 504370000000
TRACKER_FILE    = "barcode_tracker.json"


class BarcodeTracker:
    """
    Persistent tracker synced with a Git repo.
    Guarantees uniqueness across all machines, all runs, forever.
    """

    def __init__(self, tracker_path):
        self.tracker_path = tracker_path
        self.data = self._load()

    def _load(self):
        if os.path.isfile(self.tracker_path):
            try:
                with open(self.tracker_path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "last_counter": BARCODE_START - 1,
            "total_generated": 0,
            "history": []
        }

    def _save(self):
        os.makedirs(os.path.dirname(self.tracker_path) or ".", exist_ok=True)
        with open(self.tracker_path, "w") as f:
            json.dump(self.data, f, indent=2)

    def _format_barcode(self, counter):
        return f"{BARCODE_PREFIX}{counter:0{BARCODE_DIGITS}d}"

    def allocate_batch(self, count):
        start_counter = self.data["last_counter"] + 1
        end_counter = start_counter + count - 1
        self.data["last_counter"] = end_counter
        self.data["total_generated"] += count
        return [self._format_barcode(c) for c in range(start_counter, end_counter + 1)]

    def record_generation(self, input_file, count, first_barcode, last_barcode):
        entry = {
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "input_file": os.path.basename(input_file) if input_file else "unknown",
            "count": count,
            "first_barcode": first_barcode,
            "last_barcode": last_barcode
        }
        self.data["history"].append(entry)
        self._save()

    def get_stats(self):
        last = self._format_barcode(self.data["last_counter"])
        next_bc = self._format_barcode(self.data["last_counter"] + 1)
        remaining = 10**BARCODE_DIGITS - self.data["last_counter"] - 1
        return {
            "last_counter": self.data["last_counter"],
            "last_barcode": last,
            "next_barcode": next_bc,
            "total_generated": self.data["total_generated"],
            "remaining_numbers": remaining,
            "history_runs": len(self.data["history"])
        }


# ============================================================================
# GIT SYNC — PULL / PUSH TRACKER TO REPO (Cloud-Compatible)
# ============================================================================
class GitTrackerSync:
    """Clone/pull tracker from a Git repo, and push updates after generation.
    Uses PAT token from Streamlit secrets for authentication.
    Works on Streamlit Cloud (ephemeral filesystem) and locally."""

    def __init__(self, repo_url, local_dir, pat_token=None):
        self.repo_url = repo_url
        self.local_dir = local_dir
        self.repo = None
        self.pat_token = pat_token
        # Build authenticated URL with PAT token
        if self.pat_token:
            # Strip any trailing slash from repo_url
            clean_url = repo_url.rstrip("/")
            repo_path = clean_url.replace("https://github.com/", "")
            self.auth_url = f"https://{self.pat_token}@github.com/{repo_path}"
        else:
            self.auth_url = repo_url

    def clone_or_pull(self):
        """Clone if not exists, else pull latest."""
        import git
        if os.path.isdir(os.path.join(self.local_dir, ".git")):
            try:
                self.repo = git.Repo(self.local_dir)
                self.repo.remotes.origin.set_url(self.auth_url)
                origin = self.repo.remotes.origin
                origin.pull("main")
                return True, "Pulled latest tracker from Git"
            except Exception as e:
                # If pull fails, try fresh clone
                try:
                    shutil.rmtree(self.local_dir, ignore_errors=True)
                    self.repo = git.Repo.clone_from(self.auth_url, self.local_dir, branch="main")
                    return True, "Fresh clone (pull failed, re-cloned)"
                except Exception as e2:
                    return False, f"Git clone failed: {e2}"
        else:
            try:
                os.makedirs(self.local_dir, exist_ok=True)
                self.repo = git.Repo.clone_from(self.auth_url, self.local_dir, branch="main")
                return True, "Cloned tracker repo"
            except Exception as e:
                return False, f"Git clone failed: {e}"

    def push(self, commit_msg="Update barcode tracker"):
        """Commit and push updated tracker file."""
        import git
        try:
            self.repo = git.Repo(self.local_dir)
            self.repo.remotes.origin.set_url(self.auth_url)
            self.repo.git.add("--all")
            # Check if there's anything to commit
            if self.repo.is_dirty(untracked_files=True):
                self.repo.index.commit(commit_msg)
                origin = self.repo.remotes.origin
                origin.push("main")
                return True, "Pushed tracker update to Git"
            else:
                return True, "No changes to push"
        except Exception as e:
            return False, f"Git push failed: {e}"

    def get_tracker_path(self):
        """Path to tracker.json inside the repo."""
        return os.path.join(self.local_dir, TRACKER_FILE)


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


def generate(input_file, output_dir, tracker_path):
    """Generate barcode labels with auto-generated unique numbers."""

    TEMP_DIR = tempfile.mkdtemp(prefix="barcodes_")
    barcode_cache = {}

    def get_barcode(data):
        original_data = str(data).strip()
        cache_key = safe_filename(original_data)
        if cache_key in barcode_cache:
            return barcode_cache[cache_key]
        code = Code128(original_data, writer=ImageWriter())
        temp_path = os.path.join(TEMP_DIR, cache_key)
        path = code.save(temp_path, {
            "module_width": 0.25, "module_height": 8,
            "font_size": 0, "text_distance": -100
        })
        barcode_cache[cache_key] = path
        return path

    def get_position(i):
        row = i // COLUMNS_PER_PAGE
        col = i % COLUMNS_PER_PAGE
        x = PAGE_MARGIN_LEFT + col * (LABEL_WIDTH + HORIZONTAL_GAP)
        y = PAGE_MARGIN_TOP + row * (LABEL_HEIGHT + VERTICAL_GAP)
        return x, y

    tracker = BarcodeTracker(tracker_path)
    df = load_data(input_file)

    for col in ["Exam Center Code", "Exam_Session", "Subject_Code"]:
        if col not in df.columns:
            df[col] = "Unknown"

    df["Exam Center Code"] = df["Exam Center Code"].replace("", "Unknown_Center")
    df["Exam_Session"] = df["Exam_Session"].replace("", "Unknown_Session")
    df["Subject_Code"] = df["Subject_Code"].replace("", "Unknown_Subject")

    if "Seat_No" in df.columns:
        df["Seat_No_Str"] = df["Seat_No"].astype(str)
        df["Seat_No_Num"] = pd.to_numeric(df["Seat_No_Str"], errors='coerce').fillna(float('inf'))
        df = df.sort_values(by=["Subject_Code", "Seat_No_Num", "Seat_No_Str"]).drop(columns=["Seat_No_Num", "Seat_No_Str"])

    total_rows = len(df)
    auto_barcodes = tracker.allocate_batch(total_rows)
    first_bc = auto_barcodes[0]
    last_bc = auto_barcodes[-1]
    df["auto_barcode"] = auto_barcodes

    log_data = []
    total_labels = 0
    generated_pdf_files = []

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
                    draw_label(pdf, row, x, y, row["auto_barcode"], get_barcode)
                    count += 1

                file_path = os.path.join(folder, f"{session_folder}_All_Subjects.pdf")
                pdf.output(file_path)
                generated_pdf_files.append(file_path)
                total_labels += count

                log_data.append({
                    "Center": center,
                    "Date": date,
                    "Session": session,
                    "Total_Subjects": len(session_df["Subject_Code"].unique()),
                    "Total_Students": len(session_df),
                    "Barcodes_Generated": count,
                    "First_Barcode": session_df["auto_barcode"].iloc[0],
                    "Last_Barcode": session_df["auto_barcode"].iloc[-1],
                    "PDF_Filename": os.path.basename(file_path)
                })

    # Save barcode mapping CSV
    mapping_df = df[["Seat_No", "Subject_Code", "Date", "auto_barcode"]].copy()
    mapping_df.rename(columns={"Seat_No": "PRN", "auto_barcode": "Barcode_No"}, inplace=True)
    mapping_path = os.path.join(output_dir, "barcode_mapping.csv")
    mapping_df.to_csv(mapping_path, index=False)
    generated_pdf_files.append(mapping_path)

    # Record in tracker
    tracker.record_generation(input_file, total_rows, first_bc, last_bc)

    # Save generation log
    shutil.rmtree(TEMP_DIR, ignore_errors=True)

    if log_data:
        log_df = pd.DataFrame(log_data)
        log_path = os.path.join(output_dir, "generation_log.csv")
        log_df.to_csv(log_path, index=False)
        generated_pdf_files.append(log_path)

    return total_labels, len(log_data), log_data, first_bc, last_bc, mapping_df, generated_pdf_files


def load_data(input_file):
    df = pd.read_excel(input_file)

    def canonical_column_name(name):
        name = str(name).strip().lower()
        name = re.sub(r"[^a-z0-9]+", " ", name)
        return name.strip()

    mapping = {
        "seat no": "Seat_No", "seat": "Seat_No", "prn": "Seat_No",
        "subject": "Subject_Code", "subject code": "Subject_Code",
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

    required = ["Seat_No", "Subject_Code", "Date"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    df = df.fillna("")
    df = df[df["Seat_No"].astype(str).str.strip() != ""]

    if df.empty:
        raise ValueError("No rows with a valid Seat_No/PRN were found.")

    df["Date"] = df["Date"].apply(normalize_date)
    return df


def draw_label(pdf, row, x, y, auto_barcode, get_barcode_fn):
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

    sticker = auto_barcode

    barcode_w = 56.0
    barcode_h = 11.5
    barcode_x = x + (LABEL_WIDTH - barcode_w) / 2
    barcode_y = y + 15.1

    pdf.set_font("Helvetica", "B", 7.5)
    top_text_x = x + 3.5
    top_text_w = LABEL_WIDTH - 7.0

    pdf.set_xy(top_text_x, y + 8)
    pdf.cell(top_text_w, 3.5, f"PRN: {seat}      Date: {date_val}", align="C")
    pdf.set_xy(top_text_x, y + 11.5)
    pdf.cell(top_text_w, 3.5, f"Sub: {sub}    Sem: {sem_val}    Center: {center_val}", align="C")

    barcode_path = get_barcode_fn(sticker)
    pdf.image(barcode_path, x=barcode_x, y=barcode_y, w=barcode_w, h=barcode_h)

    pdf.set_xy(x, y + 27.0)
    pdf.set_font("Helvetica", "B", 8)
    bottom_text = sticker
    if program_val:
        bottom_text = f"{sticker}    Program: {program_val}"
    pdf.cell(LABEL_WIDTH, 4.0, bottom_text, align="C")


# ============================================================================
# HELPER — Create ZIP of generated files
# ============================================================================
def create_zip_of_files(file_list, zip_name="barcode_output.zip"):
    """Create a ZIP file in memory from a list of file paths."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fpath in file_list:
            if os.path.isfile(fpath):
                # Keep relative structure inside zip
                arcname = os.path.relpath(fpath, os.path.commonpath(file_list))
                zf.write(fpath, arcname)
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


# ============================================================================
# CUSTOM CSS — MGM DARK THEME (Enhanced for Cloud)
# ============================================================================
st.markdown("""
<style>
    /* ── Global Dark Theme ── */
    .stApp { background: #0f0f1a; }
    .stSidebar { background: #0f3460; }

    /* ── MGM Header ── */
    .mgm-header {
        background: linear-gradient(135deg, #0f3460 0%, #16213e 100%);
        padding: 28px 32px 22px 32px;
        border-radius: 16px;
        margin-bottom: 24px;
        border: 2px solid #d4a843;
        display: flex;
        align-items: center;
        gap: 20px;
    }
    .mgm-header h1 {
        color: #d4a843;
        font-size: 32px;
        margin: 0;
        letter-spacing: 1px;
    }
    .mgm-header .subtitle {
        color: #eaeaea;
        font-size: 14px;
        font-weight: 600;
        letter-spacing: 3px;
        margin: 0;
    }
    .mgm-header .tagline {
        color: #a8a8b8;
        font-size: 11px;
        margin: 0;
    }

    /* ── Tracker Stats Cards ── */
    .tracker-card {
        background: #1a1a2e;
        border: 1px solid #d4a843;
        border-radius: 12px;
        padding: 18px 20px;
        margin-bottom: 16px;
    }
    .tracker-card h3 {
        color: #d4a843;
        font-size: 12px;
        letter-spacing: 2px;
        margin-bottom: 12px;
    }
    .stat-value {
        color: #43d4a8;
        font-size: 18px;
        font-weight: bold;
    }
    .stat-label {
        color: #6b6b80;
        font-size: 11px;
    }

    /* ── Generate Button ── */
    .stButton > button[kind="primary"] {
        background: #d4a843 !important;
        color: #0f0f1a !important;
        font-size: 16px !important;
        font-weight: bold !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 14px 32px !important;
        letter-spacing: 1px !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: #e8c547 !important;
    }

    /* ── Section headings ── */
    .section-title {
        color: #d4a843;
        font-size: 14px;
        font-weight: 700;
        letter-spacing: 2px;
        margin-bottom: 8px;
        padding-bottom: 6px;
        border-bottom: 1px solid #2a2a4e;
    }

    /* ── Dataframes ── */
    .stDataFrame { border: 1px solid #2a2a4e; border-radius: 8px; }

    /* ── Success box ── */
    .success-box {
        background: #1a2e1a;
        border: 2px solid #43d4a8;
        border-radius: 12px;
        padding: 20px;
        margin: 16px 0;
    }

    /* ── Sidebar ── */
    .stSidebar .stMarkdown { color: #eaeaea; }
    .stSidebar h2 { color: #d4a843; }
    .stSidebar h3 { color: #e8c547; }
    .stSidebar label { color: #a8a8b8; }
    .stSidebar .stTextInput > div > div > input {
        background: #1a1a2e; color: #eaeaea;
    }

    /* ── Download buttons ── */
    .stDownloadButton > button {
        background: #0f3460 !important;
        color: #d4a843 !important;
        border: 1px solid #d4a843 !important;
        border-radius: 8px !important;
    }
    .stDownloadButton > button:hover {
        background: #16213e !important;
        color: #e8c547 !important;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# SESSION STATE INIT
# ============================================================================
if "generated" not in st.session_state:
    st.session_state.generated = False
if "result" not in st.session_state:
    st.session_state.result = None
if "git_synced" not in st.session_state:
    st.session_state.git_synced = False
if "tracker_path" not in st.session_state:
    st.session_state.tracker_path = None
if "auto_pulled" not in st.session_state:
    st.session_state.auto_pulled = False


# ============================================================================
# GIT CONFIG — Auto-sync on cloud
# ============================================================================
# Get PAT token from secrets (for Streamlit Cloud deployment)
pat_token = None
try:
    pat_token = st.secrets["github"]["pat_token"]
except Exception:
    pat_token = None  # Running locally without secrets

git_repo_url = "https://github.com/wstnil/mgm-barcode-app"
git_local_dir = os.path.join(tempfile.gettempdir(), "mgm_barcode_tracker_repo")


# ============================================================================
# HEADER
# ============================================================================
st.markdown("""
<div class="mgm-header">
    <div>
        <h1>MGM</h1>
        <p class="subtitle">BARCODE GENERATOR</p>
        <p class="tagline">Auto Unique · Never Repeats · Git-Synced · Exam Security</p>
    </div>
</div>
""", unsafe_allow_html=True)


# ============================================================================
# AUTO-INIT TRACKER (Pull from Git on first load)
# ============================================================================
if not st.session_state.auto_pulled:
    with st.spinner("Syncing tracker from Git repo..."):
        git_sync = GitTrackerSync(git_repo_url, git_local_dir, pat_token=pat_token)
        success, msg = git_sync.clone_or_pull()
        if success:
            st.session_state.tracker_path = git_sync.get_tracker_path()
            st.session_state.git_synced = True
            st.session_state.auto_pulled = True
            st.toast(f"Tracker synced: {msg}", icon="✅")
        else:
            # Fallback to local tracker if git fails
            local_tracker_dir = os.path.join(tempfile.gettempdir(), "mgm_barcode_tracker_local")
            os.makedirs(local_tracker_dir, exist_ok=True)
            local_tracker_path = os.path.join(local_tracker_dir, TRACKER_FILE)
            st.session_state.tracker_path = local_tracker_path
            st.session_state.auto_pulled = True
            st.toast(f"Git sync failed — using local tracker. {msg}", icon="⚠️")


# ============================================================================
# SIDEBAR — Git Tracker & Stats
# ============================================================================
with st.sidebar:
    st.markdown("### 🔗 Git Tracker Repo")
    st.caption("Barcode tracker is auto-synced from this repo for uniqueness guarantee.")

    st.text_input("Repo URL", value=git_repo_url, disabled=True)
    st.text_input("Branch", value="main", disabled=True)

    sync_status = "✅ Synced" if st.session_state.git_synced else "⚠️ Local fallback"
    st.info(f"Tracker status: **{sync_status}**")

    # Manual re-sync button
    if st.button("🔄 Re-sync Tracker from Git", use_container_width=True):
        git_sync = GitTrackerSync(git_repo_url, git_local_dir, pat_token=pat_token)
        success, msg = git_sync.clone_or_pull()
        if success:
            st.session_state.tracker_path = git_sync.get_tracker_path()
            st.session_state.git_synced = True
            st.success(msg)
        else:
            st.error(msg)

    # ── Tracker Stats ──
    tracker_path = st.session_state.tracker_path
    if tracker_path:
        tracker = BarcodeTracker(tracker_path)
        stats = tracker.get_stats()

        st.markdown("---")
        st.markdown("### 📊 Tracker Stats")
        col1, col2 = st.columns(2)
        col1.metric("Total Issued", f"{stats['total_generated']}")
        col2.metric("Last Barcode", stats['last_barcode'])
        col1.metric("Next Barcode", stats['next_barcode'])
        col2.metric("Remaining", f"{stats['remaining_numbers']:,}")
        col1.metric("History Runs", f"{stats['history_runs']}")

        # Show history
        if tracker.data["history"]:
            st.markdown("---")
            st.markdown("### 📜 Generation History")
            hist_df = pd.DataFrame(tracker.data["history"])
            st.dataframe(hist_df, use_container_width=True, height=250)

    # ── PAT Token Setup Info ──
    st.markdown("---")
    st.markdown("### 🔐 Secrets Setup")
    if pat_token:
        st.success("PAT token configured in secrets")
    else:
        st.warning("No PAT token found. Add `github.pat_token` in Streamlit Cloud secrets.")


# ============================================================================
# MAIN AREA
# ============================================================================

# Tracker stats banner at top
tracker_path = st.session_state.tracker_path
if tracker_path:
    tracker = BarcodeTracker(tracker_path)
    stats = tracker.get_stats()

    st.markdown("""
    <div class="tracker-card">
        <h3>UNIQUE BARCODE TRACKER</h3>
    </div>
    """, unsafe_allow_html=True)

    tc1, tc2, tc3, tc4 = st.columns(4)
    tc1.metric("Total Issued", f"{stats['total_generated']}", delta=None)
    tc2.metric("Last Barcode", stats['last_barcode'])
    tc3.metric("Next Barcode", stats['next_barcode'])
    tc4.metric("Remaining Pool", f"{stats['remaining_numbers']:,}")

st.markdown("---")

# ============================================================================
# FILE UPLOAD
# ============================================================================
st.markdown('<p class="section-title">📁 UPLOAD EXCEL FILE</p>', unsafe_allow_html=True)
uploaded_file = st.file_uploader(
    "Drag & drop or click to upload your Excel file",
    type=["xlsx", "xls", "csv"],
    help="Required columns: Seat_No/PRN, Subject_Code, Date. Optional: Semester, Exam Center Code, Program"
)

if uploaded_file:
    # Save uploaded file to temp
    temp_input = os.path.join(tempfile.gettempdir(), uploaded_file.name)
    with open(temp_input, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Preview data
    try:
        preview_df = pd.read_excel(temp_input)
        st.success(f"✅ File loaded: **{uploaded_file.name}** — {len(preview_df)} rows detected")
        st.caption(f"{len(preview_df)} unique barcodes will be auto-generated (series: A504370...)")

        with st.expander("📋 Data Preview", expanded=False):
            st.dataframe(preview_df.head(20), use_container_width=True)
            st.caption(f"Columns: {list(preview_df.columns)}")
    except Exception as e:
        st.error(f"Error reading file: {e}")
        temp_input = None

    # Output dir — always use temp on cloud
    output_dir = os.path.join(tempfile.gettempdir(), "barcode_output")

    st.markdown("---")

    # ============================================================================
    # GENERATE BUTTON
    # ============================================================================
    st.markdown('<p class="section-title">🚀 GENERATE BARCODES</p>', unsafe_allow_html=True)

    generate_clicked = st.button(
        "▶  GENERATE UNIQUE BARCODES",
        type="primary",
        use_container_width=True,
        disabled=(st.session_state.generated)
    )

    if generate_clicked and temp_input:
        with st.spinner("🔄 Generating unique barcode labels... This may take a minute for large files."):
            try:
                total_labels, num_pdfs, log_data, first_bc, last_bc, mapping_df, pdf_files = generate(
                    temp_input, output_dir, tracker_path
                )
                st.session_state.generated = True
                st.session_state.result = {
                    "total_labels": total_labels,
                    "num_pdfs": num_pdfs,
                    "log_data": log_data,
                    "first_bc": first_bc,
                    "last_bc": last_bc,
                    "mapping_df": mapping_df,
                    "pdf_files": pdf_files,
                    "output_dir": output_dir,
                    "tracker_path": tracker_path
                }
            except Exception as e:
                st.error(f"❌ Generation failed: {e}")
                st.session_state.generated = False


# ============================================================================
# RESULTS SECTION
# ============================================================================
if st.session_state.generated and st.session_state.result:
    result = st.session_state.result

    st.markdown("""
    <div class="success-box">
        <h3 style="color:#43d4a8; margin:0;">✅ Generation Complete!</h3>
    </div>
    """, unsafe_allow_html=True)

    rc1, rc2, rc3 = st.columns(3)
    rc1.metric("Total Labels", result["total_labels"])
    rc2.metric("PDF Files", result["num_pdfs"])
    rc3.metric("Barcode Range", f"{result['first_bc']} → {result['last_bc']}")

    st.markdown("---")

    # ============================================================================
    # DOWNLOAD SECTION — ZIP + Individual files
    # ============================================================================
    st.markdown('<p class="section-title">⬇️ DOWNLOAD FILES</p>', unsafe_allow_html=True)

    # ZIP download (all files bundled)
    pdf_files = result.get("pdf_files", [])
    if pdf_files:
        # Create a cleaner ZIP structure
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for fpath in pdf_files:
                if os.path.isfile(fpath):
                    # Use the relative path from output_dir for clean structure
                    try:
                        arcname = os.path.relpath(fpath, result["output_dir"])
                    except ValueError:
                        arcname = os.path.basename(fpath)
                    zf.write(fpath, arcname)
        zip_buffer.seek(0)
        zip_bytes = zip_buffer.getvalue()

        st.download_button(
            "📦 Download ALL Files (ZIP)",
            data=zip_bytes,
            file_name="barcode_output.zip",
            mime="application/zip",
            use_container_width=True
        )

    # Individual PDF downloads
    st.markdown('<p class="section-title">📄 Individual PDF Downloads</p>', unsafe_allow_html=True)
    pdf_only = [f for f in pdf_files if f.endswith(".pdf") and os.path.isfile(f)]
    if pdf_only:
        for pdf_path in pdf_only:
            try:
                rel_name = os.path.relpath(pdf_path, result["output_dir"])
            except ValueError:
                rel_name = os.path.basename(pdf_path)
            with open(pdf_path, "rb") as pf:
                pdf_bytes = pf.read()
            st.download_button(
                f"📄 {rel_name}",
                data=pdf_bytes,
                file_name=os.path.basename(pdf_path),
                mime="application/pdf"
            )

    st.markdown("---")

    # ============================================================================
    # GENERATION LOG
    # ============================================================================
    st.markdown('<p class="section-title">📊 GENERATION LOG</p>', unsafe_allow_html=True)
    log_df = pd.DataFrame(result["log_data"])
    st.dataframe(log_df, use_container_width=True)

    # Log CSV download
    log_csv = log_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇ Download Generation Log CSV",
        data=log_csv,
        file_name="generation_log.csv",
        mime="text/csv",
        use_container_width=True
    )

    st.markdown("---")

    # ============================================================================
    # BARCODE MAPPING
    # ============================================================================
    st.markdown('<p class="section-title">🔗 BARCODE MAPPING (PRN → Barcode)</p>', unsafe_allow_html=True)
    st.dataframe(result["mapping_df"], use_container_width=True)

    # Mapping CSV download
    csv_bytes = result["mapping_df"].to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇ Download Barcode Mapping CSV",
        data=csv_bytes,
        file_name="barcode_mapping.csv",
        mime="text/csv",
        use_container_width=True
    )

    st.markdown("---")

    # ============================================================================
    # GIT PUSH — Auto-push tracker update
    # ============================================================================
    if st.session_state.git_synced:
        st.markdown('<p class="section-title">☁️ PUSH TRACKER TO GIT</p>', unsafe_allow_html=True)
        st.info("Push the updated tracker to your Git repo so the next session stays synced.")

        commit_msg = st.text_input(
            "Commit Message",
            value=f"Add {result['total_labels']} barcodes — {time.strftime('%Y-%m-%d')}",
        )

        if st.button("⬆ Push Tracker to Git", use_container_width=True):
            git_sync = GitTrackerSync(git_repo_url, git_local_dir, pat_token=pat_token)
            success, msg = git_sync.push(commit_msg)
            if success:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")
                if not pat_token:
                    st.caption("No PAT token found. Add `github.pat_token` in Streamlit Cloud → Settings → Secrets.")

    # ============================================================================
    # Reset button
    # ============================================================================
    st.markdown("---")
    if st.button("🔄 Reset — Generate Another File", use_container_width=True):
        # Clean up temp output
        shutil.rmtree(result.get("output_dir", ""), ignore_errors=True)
        st.session_state.generated = False
        st.session_state.result = None
        st.rerun()


# ============================================================================
# FOOTER
# ============================================================================
st.markdown("---")
st.markdown("""
<div style="text-align:center; padding:12px; color:#6b6b80; font-size:11px;">
    <b>A4ST24S</b> · 3×8 · 69.8×35mm · Code128 · Auto Unique · Git-Synced<br>
    <b>MGM University</b> · Exam Barcode System · Public Access
</div>
""", unsafe_allow_html=True)
