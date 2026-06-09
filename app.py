import sys
import asyncio
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import sqlite3
import os

if sys.platform == 'win32':
    try: asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError: pass

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from api.main import run_nightly_triage
from fpdf import FPDF
from fpdf.enums import XPos, YPos

st.set_page_config(page_title="Aquara Triage", layout="wide", initial_sidebar_state="collapsed")

# ── ENGINE REPORT GENERATION ────────────────────────────────────────────────────

def clean_text(text):
    return str(text).encode('latin-1', 'replace').decode('latin-1')

def create_pdf_report(dataframe):
    try:
        pdf = FPDF()
        pdf.add_page()

        pdf.set_font("helvetica", style="B", size=20)
        pdf.cell(0, 15, "Aquara Leak Intelligence - Nightly Triage", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        pdf.ln(5)

        df_clean = dataframe.copy()
        df_clean['risk_score'] = pd.to_numeric(df_clean['risk_score'], errors='coerce').fillna(0)

        critical_n = len(df_clean[df_clean['risk_score'] > 0.80])
        warn_n = len(df_clean[(df_clean['risk_score'] > 0.50) & (df_clean['risk_score'] <= 0.80)])
        clear_n = len(df_clean[df_clean['risk_score'] <= 0.50])

        pdf.set_font("helvetica", style="B", size=14)
        pdf.cell(0, 10, "Executive Summary", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font("helvetica", size=11)
        summary_text = (f"The nightly diagnostic engine analyzed {len(df_clean)} total infrastructure assets. "
                        f"Currently, there are {critical_n} critical anomalies requiring immediate dispatch, "
                        f"{warn_n} assets elevated to the watch list, and {clear_n} zones validating as baseline clear.")
        pdf.multi_cell(0, 6, clean_text(summary_text))
        pdf.ln(10)

        pdf.set_font("helvetica", style="B", size=14)
        pdf.cell(0, 10, "Prioritized Action Items & Telemetry Data", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

        df_sorted = df_clean.sort_values("risk_score", ascending=False)

        for idx, row in df_sorted.iterrows():
            score = row['risk_score']

            if score > 0.80:
                status, r, g, b = "CRITICAL ALERT", 220, 38, 38
            elif score > 0.50:
                status, r, g, b = "WATCH LIST", 217, 119, 6
            else:
                status, r, g, b = "CLEAR ZONE", 22, 163, 74

            pdf.set_font("helvetica", style='B', size=11)
            pdf.set_text_color(r, g, b)
            pdf.cell(0, 8, clean_text(f"[{status}] Zone: {row['zone_id']} | Node: {row['junction_id']} | Variance: {score:.0%}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(0, 0, 0)

            pdf.set_font("helvetica", style='B', size=10)
            pdf.cell(0, 6, "Key Details: ", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("helvetica", size=10)
            pdf.multi_cell(0, 6, clean_text(row['explanation']))
            pdf.ln(2)

            pdf.set_font("helvetica", style='B', size=10)
            pdf.cell(0, 6, "Action Item:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("helvetica", size=10)
            pdf.multi_cell(0, 6, clean_text(row['work_order']))
            pdf.ln(8)

        return bytes(pdf.output())
    except Exception as e:
        return f"PDF ERROR: {str(e)}"

# ── DATABASE ─────────────────────────────────────────────────────────────────────
import shutil
from datetime import datetime

DB_PATH     = "mock_utility.db"
ARCHIVE_DIR = "db_archive"

def ensure_db():
    """Ensure the triage table exists. Never wipes data — archiving is manual only."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS triage_results (junction_id TEXT, zone_id TEXT, risk_score REAL, lat REAL, lon REAL, explanation TEXT, work_order TEXT, status TEXT)")
    conn.commit()
    conn.close()

def do_archive_and_clear():
    """Copy current DB to db_archive/ then wipe the live table. Called explicitly
    by the Clear & Archive button — never runs automatically on rerun."""
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    archive_path = os.path.join(ARCHIVE_DIR, "triage_results_last_run.db")
    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, archive_path)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM triage_results")
    conn.commit()
    conn.close()

ensure_db()

CUSTOM_KB_LIMIT = 2

# ── STYLES ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,300&display=swap');

*, *::before, *::after {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

html, body, .stApp {
    font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background: #04101f !important;
    color: #e8f0f8 !important;
    scroll-behavior: smooth;
}

#MainMenu, footer, header { visibility: hidden !important; display: none !important; }

.block-container {
    padding: 0 !important;
    max-width: 100% !important;
    width: 100% !important;
}

[data-testid="column"] > div {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}

/* ── HERO ─────────────────────────────────────────────────────── */
.hero {
    min-height: 520px;
    background: radial-gradient(ellipse 90% 65% at 50% 0%, #0a2a4a 0%, #04101f 65%);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 80px 40px 100px;
    position: relative;
    overflow: hidden;
}

.water-ring {
    position: absolute;
    border-radius: 50%;
    border: 1px solid rgba(56,189,248,0.12);
    pointer-events: none;
    animation: ripple 6s ease-out infinite;
}
.water-ring:nth-child(1) { width: 280px; height: 280px; top:50%; left:50%; transform:translate(-50%,-50%); animation-delay: 0s; }
.water-ring:nth-child(2) { width: 460px; height: 460px; top:50%; left:50%; transform:translate(-50%,-50%); animation-delay: 1.3s; }
.water-ring:nth-child(3) { width: 660px; height: 660px; top:50%; left:50%; transform:translate(-50%,-50%); animation-delay: 2.6s; }
.water-ring:nth-child(4) { width: 900px; height: 900px; top:50%; left:50%; transform:translate(-50%,-50%); animation-delay: 3.9s; }

@keyframes ripple {
    0%   { opacity: 0.7; transform: translate(-50%,-50%) scale(0.82); }
    70%  { opacity: 0.12; }
    100% { opacity: 0;   transform: translate(-50%,-50%) scale(1); }
}

.hero-orb {
    width: 72px; height: 72px;
    background: radial-gradient(circle, #38bdf8 0%, #0369a1 60%, transparent 100%);
    border-radius: 50%;
    margin-bottom: 32px;
    position: relative;
    z-index: 2;
    box-shadow: 0 0 40px rgba(56,189,248,0.55), 0 0 90px rgba(56,189,248,0.22);
    animation: orbPulse 3s ease-in-out infinite;
}

@keyframes orbPulse {
    0%, 100% { box-shadow: 0 0 40px rgba(56,189,248,0.55), 0 0 90px rgba(56,189,248,0.22); }
    50%       { box-shadow: 0 0 65px rgba(56,189,248,0.75), 0 0 140px rgba(56,189,248,0.38); }
}

.hero-eyebrow {
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: #38bdf8;
    margin-bottom: 20px;
    position: relative; z-index: 2;
    opacity: 0;
    animation: fadeUp 0.7s ease 0.3s forwards;
}

.hero-title {
    font-family: 'Syne', sans-serif;
    font-size: 58px;
    font-weight: 800;
    line-height: 1.07;
    letter-spacing: -2px;
    margin-bottom: 22px;
    position: relative; z-index: 2;
    background: linear-gradient(160deg, #ffffff 30%, #7dd3fc 70%, #38bdf8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    opacity: 0;
    animation: fadeUp 0.7s ease 0.5s forwards;
}

.hero-sub {
    font-size: 17px;
    font-weight: 300;
    color: #94a3b8;
    max-width: 500px;
    line-height: 1.75;
    position: relative; z-index: 2;
    opacity: 0;
    animation: fadeUp 0.7s ease 0.7s forwards;
}

@keyframes fadeUp {
    from { opacity: 0; transform: translateY(18px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* ── STATS STRIP ──────────────────────────────────────────────── */
.stats-strip {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    border-top: 1px solid rgba(56,189,248,0.08);
    border-bottom: 1px solid rgba(56,189,248,0.08);
}

.stat-cell {
    padding: 32px 24px;
    text-align: center;
    border-right: 1px solid rgba(56,189,248,0.08);
    position: relative;
    overflow: hidden;
}
.stat-cell:last-child { border-right: none; }
.stat-cell::before {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(ellipse 80% 60% at 50% 100%, rgba(56,189,248,0.06) 0%, transparent 70%);
    pointer-events: none;
}

.stat-num {
    font-family: 'Syne', sans-serif;
    font-size: 40px;
    font-weight: 700;
    color: #38bdf8;
    line-height: 1;
    margin-bottom: 8px;
}

.stat-label {
    font-size: 11px;
    font-weight: 400;
    color: #475569;
    letter-spacing: 2px;
    text-transform: uppercase;
}

/* ── WAVE DIVIDER ─────────────────────────────────────────────── */
.wave-divider { width: 100%; height: 52px; overflow: hidden; line-height: 0; }
.wave-divider svg { display: block; width: 100%; }

/* ── SECTIONS ─────────────────────────────────────────────────── */
.aq-section { padding: 72px 48px; }
.aq-section-sm { padding: 48px 48px 56px; }

.section-label {
    font-size: 11px;
    letter-spacing: 3px;
    text-transform: uppercase;
    font-weight: 500;
    color: #38bdf8;
    margin-bottom: 16px;
}

.section-title {
    font-family: 'Syne', sans-serif;
    font-size: 38px;
    font-weight: 700;
    letter-spacing: -0.5px;
    line-height: 1.15;
    color: #f0f6ff;
    margin-bottom: 52px;
    max-width: 520px;
}

.section-title-sm {
    font-family: 'Syne', sans-serif;
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.3px;
    color: #f0f6ff;
    margin-bottom: 8px;
}

.section-sub {
    font-size: 14px;
    font-weight: 300;
    color: #475569;
    margin-bottom: 28px;
}

/* ── PROBLEM CARDS ────────────────────────────────────────────── */
.problem-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}

.problem-card {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(56,189,248,0.08);
    border-radius: 14px;
    padding: 26px;
    transition: border-color 0.3s, background 0.3s;
    position: relative;
    overflow: hidden;
}
.problem-card::before {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(ellipse 70% 50% at 0% 100%, rgba(56,189,248,0.04) 0%, transparent 60%);
    pointer-events: none;
}
.problem-card:hover {
    border-color: rgba(56,189,248,0.24);
    background: rgba(56,189,248,0.04);
}

.pcard-icon {
    width: 38px; height: 38px;
    background: rgba(56,189,248,0.1);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    margin-bottom: 18px;
    color: #38bdf8;
    font-size: 18px;
}

.pcard-title {
    font-family: 'Syne', sans-serif;
    font-size: 15px;
    font-weight: 600;
    color: #e2eaf4;
    margin-bottom: 10px;
}

.pcard-text {
    font-size: 13px;
    font-weight: 300;
    color: #64748b;
    line-height: 1.65;
}

/* ── SOLUTION PANEL ───────────────────────────────────────────── */
.solution-panel {
    margin: 0 32px 48px;
    background: linear-gradient(135deg, #0c2744 0%, #0a1e36 100%);
    border: 1px solid rgba(56,189,248,0.16);
    border-radius: 18px;
    padding: 64px 48px;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    position: relative;
    overflow: hidden;
}
.solution-panel::before {
    content: '';
    position: absolute;
    top: -90px; left: 50%;
    transform: translateX(-50%);
    width: 480px; height: 480px;
    background: radial-gradient(circle, rgba(56,189,248,0.13) 0%, transparent 65%);
    pointer-events: none;
}

.sol-title {
    font-family: 'Syne', sans-serif;
    font-size: 44px;
    font-weight: 800;
    letter-spacing: -1.2px;
    line-height: 1.1;
    color: #f0f6ff;
    margin-bottom: 18px;
    position: relative; z-index: 1;
}

.sol-sub {
    font-size: 16px;
    font-weight: 300;
    color: #7dd3fc;
    line-height: 1.75;
    width: 100%;
    max-width: 440px;
    margin: 0 auto 36px;
    text-align: center;
    display: block;
    position: relative; z-index: 1;
}

/* ── UPLOAD ZONE ──────────────────────────────────────────────── */
.upload-shell {
    border: 1.5px dashed rgba(56,189,248,0.22);
    border-radius: 16px;
    padding: 52px 28px;
    text-align: center;
    background: rgba(56,189,248,0.025);
    transition: border-color 0.3s, background 0.3s;
    margin-bottom: 24px;
}
.upload-shell:hover {
    border-color: rgba(56,189,248,0.42);
    background: rgba(56,189,248,0.05);
}

/* ── METRIC CARDS ─────────────────────────────────────────────── */
.metric-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 40px;
}

.metric-card {
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(56,189,248,0.08);
    border-radius: 14px;
    padding: 28px 24px;
    text-align: center;
    transition: border-color 0.3s, transform 0.3s;
    position: relative;
    overflow: hidden;
}
.metric-card::before {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(ellipse 70% 60% at 50% 0%, rgba(56,189,248,0.06) 0%, transparent 65%);
    pointer-events: none;
}
.metric-card:hover {
    border-color: rgba(56,189,248,0.2);
    transform: translateY(-3px);
}

.metric-value {
    font-family: 'Syne', sans-serif;
    font-size: 44px;
    font-weight: 700;
    color: #38bdf8;
    line-height: 1;
    margin-bottom: 10px;
    position: relative; z-index: 1;
}
.metric-value.critical { color: #f87171; }
.metric-value.warning  { color: #fbbf24; }
.metric-value.clear    { color: #4ade80; }

.metric-label {
    font-size: 11px;
    font-weight: 500;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 2px;
    position: relative; z-index: 1;
}

/* ── MAP CARD ─────────────────────────────────────────────────── */
.map-card {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(56,189,248,0.08);
    border-radius: 14px;
    padding: 22px;
    margin-bottom: 20px;
}

.map-card-title {
    font-family: 'Syne', sans-serif;
    font-size: 14px;
    font-weight: 600;
    color: #94a3b8;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 16px;
}

/* ── EXPORT CARD ──────────────────────────────────────────────── */
.export-card {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(56,189,248,0.08);
    border-radius: 14px;
    padding: 26px;
    height: 100%;
}

.export-card-title {
    font-family: 'Syne', sans-serif;
    font-size: 14px;
    font-weight: 600;
    color: #94a3b8;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 8px;
}

.export-card-desc {
    font-size: 13px;
    font-weight: 300;
    color: #475569;
    margin-bottom: 32px;
    line-height: 1.6;
}

.export-btn-gap {
    height: 12px;
}

/* ── QUEUE ITEMS ──────────────────────────────────────────────── */
.queue-item {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(56,189,248,0.07);
    border-radius: 14px;
    padding: 22px 24px;
    margin-bottom: 12px;
    transition: border-color 0.3s;
}
.queue-item:hover { border-color: rgba(56,189,248,0.2); }

.q-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;
    padding-bottom: 14px;
    border-bottom: 1px solid rgba(255,255,255,0.05);
}

.q-title {
    font-family: 'Syne', sans-serif;
    font-size: 15px;
    font-weight: 600;
    color: #e2eaf4;
}

.badge {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    padding: 5px 14px;
    border-radius: 100px;
}
.badge-critical { background: rgba(239,68,68,0.14);  color: #f87171; border: 1px solid rgba(239,68,68,0.28); }
.badge-warning  { background: rgba(251,191,36,0.12); color: #fbbf24; border: 1px solid rgba(251,191,36,0.28); }
.badge-clear    { background: rgba(34,197,94,0.12);  color: #4ade80; border: 1px solid rgba(34,197,94,0.25); }

.q-risk {
    font-size: 12px;
    font-weight: 500;
    color: #64748b;
    letter-spacing: 0.5px;
    margin-bottom: 10px;
}

.progress-track {
    width: 100%;
    height: 3px;
    background: rgba(255,255,255,0.07);
    border-radius: 2px;
    overflow: hidden;
    margin-bottom: 14px;
}
.progress-fill { height: 100%; border-radius: 2px; }
.fill-critical { background: linear-gradient(90deg, #ef4444, #dc2626); }
.fill-warning  { background: linear-gradient(90deg, #f59e0b, #d97706); }
.fill-clear    { background: linear-gradient(90deg, #22c55e, #16a34a); }

.q-explanation {
    font-size: 13px;
    font-weight: 300;
    color: #64748b;
    line-height: 1.65;
    padding: 12px 14px;
    background: rgba(56,189,248,0.04);
    border-left: 2px solid rgba(56,189,248,0.28);
    border-radius: 0 8px 8px 0;
    margin-bottom: 10px;
}

.q-action {
    font-size: 12px;
    font-weight: 500;
    color: #38bdf8;
    background: rgba(56,189,248,0.06);
    padding: 10px 14px;
    border-radius: 8px;
    border: 1px solid rgba(56,189,248,0.12);
    font-family: 'DM Mono', 'Courier New', monospace;
    overflow-x: auto;
}

/* ── BUTTONS ──────────────────────────────────────────────────── */

/* Main action button (Analyze Now) — default stButton */
.stButton > button {
    background: rgba(56,189,248,0.1) !important;
    color: #38bdf8 !important;
    border: 1.5px solid rgba(56,189,248,0.35) !important;
    border-radius: 100px !important;
    padding: 14px 28px !important;
    font-family: 'Syne', sans-serif !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    cursor: pointer !important;
    transition: all 0.2s !important;
    width: 100% !important;
}
.stButton > button:hover {
    background: rgba(56,189,248,0.22) !important;
    border-color: #38bdf8 !important;
    transform: translateY(-2px) !important;
}

/* Inspect buttons use type="primary" — solid green */
.stButton > button[kind="primaryFormSubmit"],
.stButton > button[kind="primary"],
button[data-testid="baseButton-primary"] {
    background: #14532d !important;
    color: #86efac !important;
    border: 1.5px solid #22c55e !important;
    border-radius: 10px !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    letter-spacing: 0.5px !important;
    text-transform: none !important;
    padding: 10px 6px !important;
    min-height: 52px !important;
    transition: all 0.2s !important;
}
button[data-testid="baseButton-primary"]:hover {
    background: #166534 !important;
    border-color: #4ade80 !important;
    color: #ffffff !important;
    transform: scale(1.05) !important;
}

/* Also catch Streamlit's own .st-emotion-cache primary overrides */
[data-testid="stBaseButton-primary"] {
    background: #14532d !important;
    color: #86efac !important;
    border: 1.5px solid #22c55e !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    min-height: 52px !important;
}
[data-testid="stBaseButton-primary"]:hover {
    background: #166534 !important;
    color: #ffffff !important;
    border-color: #4ade80 !important;
}

.stDownloadButton > button {
    background: rgba(56,189,248,0.08) !important;
    color: #38bdf8 !important;
    border: 1px solid rgba(56,189,248,0.22) !important;
    border-radius: 100px !important;
    padding: 12px 24px !important;
    font-family: 'Syne', sans-serif !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    letter-spacing: 1.2px !important;
    text-transform: uppercase !important;
    width: 100% !important;
    margin-bottom: 10px !important;
    transition: background 0.2s, border-color 0.2s, transform 0.2s !important;
}
.stDownloadButton > button:hover {
    background: rgba(56,189,248,0.15) !important;
    border-color: rgba(56,189,248,0.45) !important;
    transform: translateY(-2px) !important;
}

/* ── FILE UPLOADER ────────────────────────────────────────────── */
/* Hide Streamlit's default size hint (shows platform max, not our limit) */
.stFileUploader small { display: none !important; }
.stFileUploader [data-testid="stFileUploadDropzone"] small { display: none !important; }
[data-testid="stFileUploaderDropzoneInstructions"] small,
[data-testid="stFileUploaderDropzoneInstructions"] span[class*="fileSize"] { display: none !important; }

.stFileUploader [data-testid="stFileUploadDropzone"] {
    background: rgba(56,189,248,0.03) !important;
    border: 1.5px dashed rgba(56,189,248,0.3) !important;
    border-radius: 16px !important;
    padding: 40px 20px !important;
    transition: all 0.3s ease !important;
}
.stFileUploader [data-testid="stFileUploadDropzone"]:hover {
    border-color: rgba(56,189,248,0.55) !important;
    background: rgba(56,189,248,0.07) !important;
}

/* All text inside the dropzone (instructions, limits) */
.stFileUploader [data-testid="stFileUploadDropzone"] * {
    color: #7dd3fc !important;
}
.stFileUploader [data-testid="stFileUploadDropzone"] p,
.stFileUploader [data-testid="stFileUploadDropzone"] span,
.stFileUploader [data-testid="stFileUploadDropzone"] div {
    color: #94a3b8 !important;
}

/* The uploaded file chip */
.stFileUploader [data-testid="stFileUploaderFile"] {
    background: rgba(56,189,248,0.08) !important;
    border: 1px solid rgba(56,189,248,0.2) !important;
    border-radius: 10px !important;
    color: #e2eaf4 !important;
}
.stFileUploader [data-testid="stFileUploaderFileName"] {
    color: #e2eaf4 !important;
}
.stFileUploader [data-testid="stFileUploaderFileData"] {
    color: #64748b !important;
}

.stFileUploader button {
    background: rgba(56,189,248,0.1) !important;
    border: 1px solid rgba(56,189,248,0.3) !important;
    border-radius: 100px !important;
    color: #38bdf8 !important;
    font-weight: 600 !important;
    padding: 10px 20px !important;
    font-size: 12px !important;
    transition: all 0.3s ease !important;
}
.stFileUploader button:hover {
    border-color: rgba(56,189,248,0.55) !important;
    background: rgba(56,189,248,0.18) !important;
}

/* ── STATUS MESSAGES ──────────────────────────────────────────── */
.stSuccess {
    background: rgba(34,197,94,0.08) !important;
    color: #4ade80 !important;
    border: 1px solid rgba(34,197,94,0.25) !important;
    border-radius: 12px !important;
}
.stError {
    background: rgba(239,68,68,0.08) !important;
    color: #f87171 !important;
    border: 1px solid rgba(239,68,68,0.25) !important;
    border-radius: 12px !important;
}
.stWarning {
    background: rgba(251,191,36,0.08) !important;
    color: #fbbf24 !important;
    border: 1px solid rgba(251,191,36,0.25) !important;
    border-radius: 12px !important;
}
.stInfo {
    background: rgba(56,189,248,0.08) !important;
    color: #7dd3fc !important;
    border: 1px solid rgba(56,189,248,0.22) !important;
    border-radius: 12px !important;
}

/* ── EMPTY STATE ──────────────────────────────────────────────── */
.empty-state {
    text-align: center;
    padding: 100px 20px;
}
.empty-orb {
    width: 56px; height: 56px;
    background: radial-gradient(circle, rgba(56,189,248,0.3) 0%, transparent 70%);
    border-radius: 50%;
    margin: 0 auto 20px;
    border: 1px solid rgba(56,189,248,0.2);
}
.empty-title {
    font-family: 'Syne', sans-serif;
    font-size: 22px;
    font-weight: 700;
    color: #334155;
    margin-bottom: 10px;
}
.empty-text {
    font-size: 14px;
    font-weight: 300;
    color: #334155;
    line-height: 1.7;
    max-width: 340px;
    margin: 0 auto;
}

/* ── DIVIDER ──────────────────────────────────────────────────── */
.aq-divider {
    border: none;
    border-top: 1px solid rgba(56,189,248,0.07);
    margin: 0;
}

/* ── FOOTER ───────────────────────────────────────────────────── */
.footer-strip {
    border-top: 1px solid rgba(56,189,248,0.07);
    padding: 24px 48px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(0,0,0,0.2);
}
.footer-brand {
    font-family: 'Syne', sans-serif;
    font-size: 16px;
    font-weight: 800;
    color: #38bdf8;
    letter-spacing: 2px;
}
.footer-links {
    display: flex;
    gap: 28px;
}
.footer-link {
    font-size: 11px;
    color: #334155;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-weight: 400;
    cursor: pointer;
    transition: color 0.2s;
    text-decoration: none;
}
.footer-link:hover { color: #7dd3fc; }
</style>
""", unsafe_allow_html=True)

# ── APP STATE ─────────────────────────────────────────────────────────────────
conn = sqlite3.connect("mock_utility.db")
df_all = pd.read_sql_query("SELECT * FROM triage_results WHERE status != 'INSPECTED'", conn)
conn.close()

# ── HERO ──────────────────────────────────────────────────────────────────────
st.markdown("""
<section class="hero">
    <div class="water-ring"></div>
    <div class="water-ring"></div>
    <div class="water-ring"></div>
    <div class="water-ring"></div>
    <div class="hero-orb"></div>
    <div class="hero-eyebrow">Leak Detection Intelligence</div>
    <h1 class="hero-title">Stop Searching.<br>Start Prioritizing.</h1>
    <p class="hero-sub">AI-powered triage that ranks the most likely leak zones and builds actionable inspection queues—instantly.</p>
</section>
""", unsafe_allow_html=True)

# ── STATS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="stats-strip">
    <div class="stat-cell">
        <div class="stat-num">2.1T</div>
        <div class="stat-label">Gallons Lost / yr</div>
    </div>
    <div class="stat-cell">
        <div class="stat-num">2 Mins</div>
        <div class="stat-label">Average Water Main Break</div>
    </div>
    <div class="stat-cell">
        <div class="stat-num">$7.6B</div>
        <div class="stat-label">Annual Revenue Lost (US)</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── WAVE ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="wave-divider">
    <svg viewBox="0 0 1440 52" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M0,26 Q360,52 720,26 T1440,26 L1440,52 L0,52 Z" fill="rgba(56,189,248,0.04)"/>
        <path d="M0,34 Q360,10 720,34 T1440,34 L1440,52 L0,52 Z" fill="rgba(56,189,248,0.03)"/>
    </svg>
</div>
""", unsafe_allow_html=True)

# ── PROBLEM ───────────────────────────────────────────────────────────────────
st.markdown("""
<section class="aq-section">
    <div class="section-label">The Challenge</div>
    <h2 class="section-title">Field teams search in the dark, <br>every hour counts.</h2>
    <div class="problem-grid">
        <div class="problem-card">
            <div class="pcard-icon">🔍</div>
            <div class="pcard-title">Blind Search</div>
            <div class="pcard-text">Crews spend hours chasing unvalidated leads with no data-driven prioritization, missing real leaks in the process.</div>
        </div>
        <div class="problem-card">
            <div class="pcard-icon">⚠️</div>
            <div class="pcard-title">False Alarms</div>
            <div class="pcard-text">Manual monitoring creates too many positives, wasting time and resources on low-risk zones.</div>
        </div>
        <div class="problem-card">
            <div class="pcard-icon">📊</div>
            <div class="pcard-title">Scattered Data</div>
            <div class="pcard-text">GIS, billing, and SCADA data sit in silos, insights never reach the field as actionable intelligence.</div>
        </div>
        <div class="problem-card">
            <div class="pcard-icon">💰</div>
            <div class="pcard-title">Hidden Costs</div>
            <div class="pcard-text">Undetected leaks drain revenue, inflate emergency response costs, and damage customer trust.</div>
        </div>
    </div>
</section>
""", unsafe_allow_html=True)

# ── SOLUTION ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="solution-panel">
    <h2 class="sol-title">Triage, Don't Search</h2>
    <p class="sol-sub" style="text-align:center !important; margin-left:auto !important; margin-right:auto !important; display:block !important;">Ingest your GIS, billing, and work order data. We rank the most likely leak zones, explain why, and deliver a prioritized inspection queue. Your team goes straight to the source.</p>
</div>
""", unsafe_allow_html=True)

# ── UPLOAD ────────────────────────────────────────────────────────────────────
st.markdown("""
<section class="aq-section-sm">
    <div class="section-label">Upload & Analyze</div>
    <div class="section-title-sm">Drop your telemetry data</div>
    <div class="section-sub">CSV · JSON · GeoJSON · TXT etc. large files sampled to first 6 rows</div>
</section>
""", unsafe_allow_html=True)

# Track uploader key in session state so we can reset it programmatically
if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0

col_left, col_center, col_right = st.columns([1, 2, 1])
with col_center:
    uploaded_files = st.file_uploader(
        "Upload files",
        accept_multiple_files=True,
        label_visibility="collapsed",
        key=f"uploader_{st.session_state['uploader_key']}"
    )

    oversized_detected = False
    staged_count = 0
    sampled_files = []
    if uploaded_files:
        import tempfile, shutil, io
        os.makedirs("sample_data", exist_ok=True)

        def sample_file_bytes(file, max_lines=6):
            """Return a byte slice of file containing at most max_lines lines.
            Works for CSV, TSV, TXT, GeoJSON, and plain JSON (line-delimited).
            For binary/non-line-based formats falls back to a raw byte cap."""
            raw = file.getbuffer()
            ext = os.path.splitext(file.name)[1].lower()
            if ext in (".csv", ".tsv", ".txt", ".geojson", ".json", ".ndjson"):
                try:
                    text = bytes(raw).decode("utf-8", errors="replace")
                    lines = text.splitlines(keepends=True)
                    sampled = "".join(lines[:max_lines])
                    return sampled.encode("utf-8")
                except Exception:
                    pass
            return bytes(raw)[: CUSTOM_KB_LIMIT * 1024]

        for file in uploaded_files:
            dest = os.path.join("sample_data", file.name)
            is_oversized = file.size > CUSTOM_KB_LIMIT * 1024

            if is_oversized:
                data_to_write = sample_file_bytes(file)
                sampled_files.append(file.name)
            else:
                data_to_write = bytes(file.getbuffer())

            try:
                fd, tmp_path = tempfile.mkstemp(dir="sample_data")
                try:
                    with os.fdopen(fd, "wb") as tmp:
                        tmp.write(data_to_write)
                    shutil.move(tmp_path, dest)
                    staged_count += 1
                except Exception:
                    os.unlink(tmp_path)
                    raise
            except PermissionError:
                st.warning(f"⚠️ Could not write {file.name} — file may be open elsewhere. Close it and retry.")
                oversized_detected = True

        if oversized_detected:
            st.error("⚠️ One or more files could not be written (locked). Close them and retry.")
        else:
            if sampled_files:
                st.info(f"✂️ Large file(s) sampled to first 6 lines: {', '.join(sampled_files)}")
            st.success(f"✓ Successfully staged {staged_count} file(s)")

    # Clear uploaded files button — resets the uploader widget
    if uploaded_files:
        if st.button("✕  Clear uploaded files", use_container_width=True):
            st.session_state["uploader_key"] += 1
            # Also remove staged files from disk
            if os.path.exists("sample_data"):
                for f in os.listdir("sample_data"):
                    try: os.remove(os.path.join("sample_data", f))
                    except: pass
            st.rerun()

# ── ENGINE ────────────────────────────────────────────────────────────────────
st.markdown("""
<section class="aq-section-sm" style="padding-top: 0;">
    <div class="section-label">Analyze</div>
    <div class="section-title-sm">Run the Engine</div>
    <div class="section-sub">Process your data and generate a prioritized leak triage report</div>
</section>
""", unsafe_allow_html=True)

col_left, col_center, col_right = st.columns([1, 2, 1])
with col_center:
    if st.button("▶  Analyze Now", use_container_width=True):
        if not uploaded_files or staged_count == 0:
            st.error("✗ No valid files to process. Please upload telemetry data first.")
        else:
            st.info("⚙️ Processing telemetry data and analyzing anomalies...")
            with st.spinner("Running diagnostic engine..."):
                engine_status = run_nightly_triage()
            if engine_status and engine_status.get("status") == "unsuitable":
                st.error("✗ Data validation failed. Please check file format and structure.")
            elif engine_status and engine_status.get("status") == "malformed_json":
                st.error("✗ JSON parsing error. Please verify your JSON files are valid.")
            else:
                st.rerun()

# ── REFRESH ───────────────────────────────────────────────────────────────────
conn = sqlite3.connect("mock_utility.db")
df_all = pd.read_sql_query("SELECT * FROM triage_results WHERE status != 'INSPECTED'", conn)
conn.close()

# ── RESULTS ───────────────────────────────────────────────────────────────────
if not df_all.empty:

    # Section header
    st.markdown("""
    <section class="aq-section-sm" style="padding-bottom: 28px;">
        <div class="section-label">Results</div>
        <div class="section-title-sm">Your Inspection Queue</div>
        <div class="section-sub">Review risk assessment, export reports, and start inspections</div>
    </section>
    """, unsafe_allow_html=True)

    # Metrics
    critical_n = len(df_all[df_all['risk_score'] > 0.80])
    warn_n     = len(df_all[(df_all['risk_score'] > 0.50) & (df_all['risk_score'] <= 0.80)])
    ok_n       = len(df_all[df_all['risk_score'] <= 0.50])

    pad_l, col1, col2, col3, pad_r = st.columns([0.1, 1, 1, 1, 0.1])
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value critical">{critical_n}</div>
            <div class="metric-label">Critical</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value warning">{warn_n}</div>
            <div class="metric-label">Watch List</div>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value clear">{ok_n}</div>
            <div class="metric-label">Clear</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height: 32px'></div>", unsafe_allow_html=True)

    # Map + Exports
    pad_l, col_map, col_exports, pad_r = st.columns([0.05, 1.6, 0.9, 0.05])

    with col_map:
        st.markdown('<div class="map-card"><div class="map-card-title">📍 Risk Distribution Map</div>', unsafe_allow_html=True)

        # Map shows ALL results with valid coords (including CLEAR) — not just queue items
        _map_conn = sqlite3.connect("mock_utility.db")
        df_map = pd.read_sql_query("SELECT * FROM triage_results WHERE lat IS NOT NULL AND lon IS NOT NULL", _map_conn)
        _map_conn.close()

        if df_map.empty:
            st.info("No coordinate data available to map.")
        else:
            # Fit map to the actual bounds of the data
            lat_min, lat_max = df_map['lat'].min(), df_map['lat'].max()
            lon_min, lon_max = df_map['lon'].min(), df_map['lon'].max()
            map_center = [(lat_min + lat_max) / 2, (lon_min + lon_max) / 2]

            # Pick zoom based on coordinate spread — tighter data = higher zoom
            lat_span = lat_max - lat_min
            lon_span = lon_max - lon_min
            max_span = max(lat_span, lon_span)
            if max_span < 0.01:   zoom = 15
            elif max_span < 0.05: zoom = 14
            elif max_span < 0.15: zoom = 13
            elif max_span < 0.5:  zoom = 12
            elif max_span < 2.0:  zoom = 10
            else:                 zoom = 8

            m = folium.Map(location=map_center, zoom_start=zoom, tiles="CartoDB positron")

            for _, row in df_map.iterrows():
                score = row['risk_score']
                if score > 0.80:   marker_color = "red"
                elif score > 0.50: marker_color = "orange"
                else:              marker_color = "green"

                status_label = "INSPECTED" if row['status'] == 'INSPECTED' else (
                    "Critical" if score > 0.80 else "Watch" if score > 0.50 else "Clear"
                )
                popup_html = (
                    f"<div style=\"font-family:'DM Sans',sans-serif;font-size:13px;color:#0f1419;\">"
                    f"<strong>{row['junction_id']}</strong><br>"
                    f"Zone: {row['zone_id']}<br>"
                    f"Risk: {score:.0%} — {status_label}</div>"
                )
                folium.Marker(
                    location=[row["lat"], row["lon"]],
                    popup=folium.Popup(popup_html, max_width=220),
                    tooltip=f"{row['junction_id']} ({score:.0%})",
                    icon=folium.Icon(color=marker_color, icon="tint", prefix="fa")
                ).add_to(m)

            # The dynamic key forces the browser to redraw the map from scratch whenever an item is cleared
        # 🌟 FIX: Dynamic key forces the map to redraw completely so old pins disappear!
        map_key = f"risk_map_{len(df_all)}_{df_all['risk_score'].sum()}"
        st_folium(m, height=440, use_container_width=True, key=map_key)
        
        st.markdown('</div>', unsafe_allow_html=True)

    with col_exports:
        pdf_data = create_pdf_report(df_all)
        csv_bytes = df_all.to_csv(index=False).encode("utf-8")

        st.markdown('<div class="export-card"><div class="export-card-title">📥 Export Data</div><div class="export-card-desc">Download your inspection queue in your preferred format</div></div>', unsafe_allow_html=True)

        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

        st.download_button(
            label="↓  CSV Report",
            data=csv_bytes,
            file_name="aquara_triage.csv",
            mime="text/csv",
            use_container_width=True
        )

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

        if isinstance(pdf_data, str) and pdf_data.startswith("PDF ERROR"):
            st.error("PDF generation failed")
        else:
            st.download_button(
                label="↓  PDF Report",
                data=pdf_data,
                file_name="aquara_triage.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
        st.markdown('<div class="export-card-title" style="margin-bottom:8px;">🗄️ Archive & Clear</div>', unsafe_allow_html=True)
        st.markdown('<div class="export-card-desc">Save current results to archive and reset the queue for a new analysis run.</div>', unsafe_allow_html=True)
        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
        if st.button("⬆  Archive & Clear Queue", use_container_width=True, key="archive_btn"):
            do_archive_and_clear()
            st.session_state["uploader_key"] += 1   # also reset the file uploader
            st.success("✓ Results archived to db_archive/. Queue cleared.")
            st.rerun()

    st.markdown("<div style='height: 48px'></div>", unsafe_allow_html=True)

    # Queue
    st.markdown("""
    <section class="aq-section-sm" style="padding-bottom: 16px;">
        <div class="section-label">Priority Queue</div>
        <div class="section-title-sm">Inspection Order</div>
        <div class="section-sub">Zones ranked by risk level — mark each as inspected when complete</div>
    </section>
    """, unsafe_allow_html=True)

    pad_l, col_queue, pad_r = st.columns([0.05, 1, 0.05])
    with col_queue:
        # Only show actionable items in the queue — Clear zones don't need dispatch
        queue_df = df_all[df_all['risk_score'] > 0.50].sort_values("risk_score", ascending=False)

        if queue_df.empty:
            st.markdown("""
            <div style="text-align:center; padding: 48px 20px; color: #4ade80;">
                <div style="font-size: 32px; margin-bottom: 12px;">✓</div>
                <div style="font-family:'Syne',sans-serif; font-size: 18px; font-weight: 700; margin-bottom: 8px;">All Clear</div>
                <div style="font-size: 13px; color: #475569;">No critical or watch-list zones detected in this dataset.</div>
            </div>
            """, unsafe_allow_html=True)

        for idx, row in queue_df.iterrows():
            score = row["risk_score"]
            if score > 0.80:
                badge_class, badge_text, bar_class = "badge-critical", "Critical", "fill-critical"
            elif score > 0.50:
                badge_class, badge_text, bar_class = "badge-warning", "Watch", "fill-warning"
            else:
                badge_class, badge_text, bar_class = "badge-clear", "Clear", "fill-clear"

            col_item, col_btn = st.columns([10, 1])

            with col_item:
                st.markdown(f"""
                <div class="queue-item">
                    <div class="q-header">
                        <div class="q-title">{row["zone_id"]} — {row["junction_id"]}</div>
                        <span class="badge {badge_class}">{badge_text}</span>
                    </div>
                    <div class="q-risk">Risk Variance: {score:.1%}</div>
                    <div class="progress-track">
                        <div class="progress-fill {bar_class}" style="width:{int(score * 100)}%"></div>
                    </div>
                    <div class="q-explanation">{row["explanation"]}</div>
                    <div class="q-action">📋 {row["work_order"]}</div>
                </div>
                """, unsafe_allow_html=True)

            with col_btn:
                st.markdown(f"<div style='padding-top: 26px;'></div>", unsafe_allow_html=True)
                if st.button("✓ Done", key=f"btn_{idx}_{row['junction_id']}", use_container_width=True, type="primary", help="Mark this zone as inspected and remove from queue"):
                    conn = sqlite3.connect("mock_utility.db")
                    conn.execute("UPDATE triage_results SET status = 'INSPECTED' WHERE junction_id = ?", (row["junction_id"],))
                    conn.commit()
                    conn.close()
                    st.cache_data.clear()
                    st.rerun()

        # 🌟 FIX: NEW ARCHIVE CLEAR BUTTON 🌟
        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
                
                # Check if the DB has any items actively marked as 'INSPECTED'
        conn = sqlite3.connect("mock_utility.db")
        try:
            archived_count = pd.read_sql_query("SELECT COUNT(*) FROM triage_results WHERE status = 'INSPECTED'", conn).iloc[0,0]
        except Exception:
            archived_count = 0
        conn.close()

                # If they exist, display the dedicated purge button!
        if archived_count > 0:
            if st.button(f"🗑️ Clear Inspected Archive ({archived_count} Items)", use_container_width=True):
                conn = sqlite3.connect("mock_utility.db")
                conn.execute("DELETE FROM triage_results WHERE status = 'INSPECTED'")
                conn.commit()
                conn.close()
                st.cache_data.clear()
                st.rerun()

else:
    # Empty state
    st.markdown("""
    <div class="empty-state">
        <div class="empty-orb"></div>
        <div class="empty-title">No Results Yet</div>
        <div class="empty-text">Upload telemetry data and run the analysis to see your prioritized leak triage queue.</div>
    </div>
    """, unsafe_allow_html=True)

# ── FOOTER ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="footer-strip">
    <div class="footer-brand">AQUARA</div>
    <div class="footer-links">
        <a class="footer-link" href="#">Docs</a>
        <a class="footer-link" href="#">API</a>
        <a class="footer-link" href="#">Support</a>
    </div>
</div>
""", unsafe_allow_html=True)