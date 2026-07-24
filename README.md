# 🏫 MGM Barcode Generator

**Auto-unique barcode label generator for exam sticker sheets.**  
Every barcode is **globally unique, never repeats, Git-synced** across machines and days.

---

## ✨ Features

| Feature | Details |
|---------|---------|
| **Auto-Generated Barcodes** | A-prefix + 12-digit sequential (`A504370000000` → `A504370002428`) |
| **Never Repeats** | 495 billion numbers in pool — even months later, zero duplication |
| **Git-Synced Tracker** | `barcode_tracker.json` lives in a Git repo — cross-machine uniqueness |
| **Audit Log** | Every generation run recorded with date, file, first/last barcode |
| **PRN → Barcode Mapping** | CSV export maps every student PRN to their barcode |
| **A4ST24S Labels** | 3×8 grid, 69.8×35mm — Code128 barcodes on A4 sheets |
| **Two UIs** | Desktop (Tkinter) + Web (Streamlit) |

---

## 📦 Required Columns in Excel

Your Excel file must have these columns (names are auto-detected):

| Required | Accepted Column Names |
|----------|----------------------|
| **Seat_No / PRN** | `Seat No`, `Seat`, `PRN`, `Seat No.` |
| **Subject_Code** | `Subject Code`, `Subject` |
| **Date** | `Date`, `Exam Date` |

Optional (used if present):

| Optional | Accepted Column Names |
|----------|----------------------|
| **Semester** | `Semester`, `Sem` |
| **Exam Center Code** | `Exam Center Code`, `Center`, `Centre`, `College Code` |
| **Exam Time / Session** | `Exam Time`, `Time`, `Session` |
| **Program** | `Program`, `Branch`, `Stream`, `Degree` |

> **Sticker_No and Division columns are NOT needed** — barcodes are auto-generated.

---

## 🖥️ Desktop App (Tkinter GUI)

### Install

```bash
pip install -r requirements.txt
```

### Run

```bash
python barcode_gui.py
```

### Usage

1. **Drag & drop** your Excel file onto the drop zone (or click to browse)
2. Pick an **output folder** (auto-set next to input file)
3. Click **▶ GENERATE BARCODES**
4. PDFs generated in: `output_folder/Center/Date/Session/`
5. Tracker stats auto-refresh after generation

---

## 🌐 Web App (Streamlit)

### Install

```bash
pip install -r requirements.txt
```

### Run

```bash
streamlit run barcode_streamlit.py
```

### Usage

1. Open browser → `http://localhost:8501`
2. In sidebar: enter **Git repo URL** → click **Pull Tracker**
3. Upload your Excel file
4. Set output folder path
5. Click **▶ GENERATE UNIQUE BARCODES**
6. Download barcode mapping CSV from the results page
7. Click **⬆ Push Tracker to Git** to sync the tracker

---

## 🔗 Git Tracker Setup

The barcode tracker (`barcode_tracker.json`) guarantees uniqueness across all machines.  
Set up a Git repo to sync it:

### 1. Create a GitHub repo

```
https://github.com/<your-org>/mgm-barcode-tracker
```

### 2. Configure in Streamlit sidebar

Enter the repo URL → Pull → Generate → Push

### 3. Git credentials

For PAT token authentication:

```bash
git config --global credential.helper store
```

Then when pushing, use your PAT token as the password.

### How it works

```
Machine A: Pull tracker → Generate 500 barcodes → Push tracker
Machine B: Pull tracker (now knows 500 already used) → Generate 200 more → Push tracker
Machine A (next month): Pull → Counter continues from 700 → Never duplicates
```

---

## 📁 Output Structure

Generated PDFs are organized by exam center, date, and session:

```
barcode_output/
├── JNEC/
│   └── 13_06_2026/
│       └── 10_00_00.0-12_00_00.0/
│           └── 10_00_00.0-12_00_00.0_All_Subjects.pdf
├── IBT/
│   └── 13_06_2026/
│       └── 10_00_00.0-12_00_00.0/
│           └── 10_00_00.0-12_00_00.0_All_Subjects.pdf
├── barcode_mapping.csv          ← PRN → Barcode mapping
├── generation_log.csv           ← Per-group statistics
└── barcode_tracker.json         ← Uniqueness tracker
```

---

## 🏷️ Label Layout

Each sticker label (69.8 × 35 mm) contains:

```
┌─────────────────────────────────┐
│  PRN: 202401105008   Date: 13/06│  ← Student info
│  Sub: ECE21PCL252  Sem: 4  C:3 │  ← Subject + Semester + Center
│  ██████████████████████████████ │  ← Code128 Barcode (auto-generated)
│  A504370000000  Program: 437    │  ← Barcode number + Program
└─────────────────────────────────┘
```

---

## 🔒 Uniqueness Guarantee

| Scenario | Result |
|----------|--------|
| Same file, same day | All barcodes different (sequential) |
| Different file, next day | Counter continues — no overlap |
| Different machine, next month | Git-synced tracker — same counter |
| 10 years later | Still unique — 495 billion numbers available |

---

## 🛠️ Tech Stack

- **Python 3.12+**
- **fpdf2** — PDF generation
- **python-barcode** — Code128 barcode rendering
- **Pillow** — Image processing
- **pandas** — Excel data handling
- **tkinterdnd2** — Drag & drop desktop UI
- **Streamlit** — Web-based UI
- **GitPython** — Git tracker sync

---

## 📄 License

MGM University — Internal Exam System Tool

---

## 👨‍💻 Maintained By

MGM University IT Team  
Exam Barcode Security System
