import sys
import asyncio

if sys.platform == 'win32':
    try: asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError: pass

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import sqlite3
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from api.main import run_nightly_triage
from fpdf import FPDF
from fpdf.enums import XPos, YPos

st.set_page_config(page_title="Aquara", layout="wide")

def init_db():
    conn = sqlite3.connect("mock_utility.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS triage_results (junction_id TEXT, zone_id TEXT, risk_score REAL, lat REAL, lon REAL, explanation TEXT, work_order TEXT, status TEXT)")
    conn.commit()
    conn.close()

init_db()

def create_pdf_report(dataframe):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("helvetica", style="B", size=18)
        pdf.cell(0, 10, "Aquara Leak Triage Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        pdf.ln(5)
        for idx, row in dataframe.iterrows():
            pdf.set_font("helvetica", style='B', size=12)
            pdf.cell(0, 8, f"Zone: {row['zone_id']} | Asset: {row['junction_id']} | Risk: {row['risk_score']:.0%}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("helvetica", size=10)
            pdf.multi_cell(0, 6, f"AI Explanation: {row['explanation']}\nWork Order: {row['work_order']}")
            pdf.ln(5)
        return bytes(pdf.output()) 
    except Exception as e: return f"Error: {str(e)}".encode('utf-8')

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,700&display=swap');
.stApp { font-family: 'DM Sans', sans-serif !important; background: linear-gradient(175deg, #069ab8 0%, #083040 55%, #041e2a 100%) !important; color: white !important; }
#MainMenu, footer, header {visibility: hidden !important; display: none !important;}
.block-container {padding: 1.5rem 2rem 2rem !important;}
[data-testid="column"] > div { background: rgba(240, 253, 255, 0.28) !important; backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.65) !important; border-top: 2px solid rgba(255, 255, 255, 0.88) !important; border-radius: 14px !important; padding: 15px !important; }
.header-title { font-size: 28px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin: 0;}
.header-sub { font-size: 13px; font-weight: 500; color: #ffffff; letter-spacing: 0.05em; margin-top: 2px; }
.section-label { font-size: 15px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; border-bottom: 2px solid white; padding-bottom: 6px; margin-bottom: 12px; margin-top: 10px;}
.stButton > button { width: 100% !important; font-size: 13px !important; font-weight: 700 !important; text-transform: uppercase !important; color: #083040 !important; border-radius: 7px !important; padding: 6px !important; border-top: 1.5px solid rgba(255,255,255,0.95) !important; background: linear-gradient(175deg, rgba(255,255,255,0.92) 0%, rgba(155,238,255,0.8) 55%, rgba(207,248,255,0.88) 100%) !important; }
.stDownloadButton > button { background: linear-gradient(175deg, rgba(255,255,255,0.92) 0%, rgba(167,243,208,0.82) 55%, rgba(209,250,229,0.9) 100%) !important; border-color: rgba(16,185,129,0.35) !important; color: #033d1c !important; width: 100%; font-weight: 700 !important;}

div[data-testid="stFileUploader"] section small, div[data-testid="stFileUploaderDropzone"] small, div[data-testid="stFileUploadDropzone"] div div small, div[data-testid="stUploadDropzoneDescription"] div:last-child, .stFileUploader section div div small { display: none !important; opacity: 0 !important; height: 0px !important; visibility: hidden !important; font-size: 0px !important; }
[data-testid="stFileUploadDropzone"]::after { content: "Drag and drop telemetry files here\\A (Hardware Limit: 2 KB per file)" !important; white-space: pre-wrap !important; font-size: 14px !important; color: #ffffff !important; font-weight: 700 !important; display: block !important; line-height: 1.5 !important; }
[data-testid="stFileUploadDropzone"] { border: 2px dashed #18c5e8 !important; border-radius: 8px !important; background: rgba(8, 48, 64, 0.75) !important; padding: 24px 8px !important; text-align: center !important; display: block !important; }

.status-row { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #ffffff; padding: 4px 0; font-weight: 700;}
.dot { width: 8px; height: 8px; border-radius: 50%; } .dot-g { background: #10b981; } .dot-b { background: #18c5e8; } .dot-r { background: #ef4444; }
.metric { background: rgba(220,248,255,0.42); border: 1px solid rgba(152,236,255,0.35); border-radius: 9px; padding: 8px 10px; margin-bottom: 6px; display: flex; justify-content: space-between; align-items: center;}
.mlabel { font-size: 13px; font-weight: 700; } .mval { font-size: 20px; font-weight: 700; }
.queue-item { background: rgba(240,253,255,0.42); border: 1px solid rgba(255,255,255,0.3); border-radius: 9px; padding: 12px; margin-bottom: 10px; }
.qi-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 4px;}
.qi-name { font-size: 14px; font-weight: 700; }
.badge { font-size: 10px; font-weight: 700; text-transform: uppercase; padding: 2px 8px; border-radius: 999px; }
.badge-r { background: #ef4444; } .badge-a { background: #f59e0b; } .badge-g { background: #10b981; }
.pbar-bg { background: rgba(255,255,255,0.2); border-radius: 999px; height: 6px; margin: 8px 0; overflow: hidden; }
.pbar { height: 100%; }
.qi-exp { font-size: 12px; line-height: 1.45; background: rgba(0,0,0,0.15); border-radius: 6px; padding: 8px; margin-bottom: 6px; }
.qi-code { font-size: 11px; font-weight: 600; color: #a0eeff; background: rgba(2,20,36,0.6); border-radius: 5px; padding: 8px; font-family: monospace; border-left: 3px solid #18c5e8;}
.qi-var { font-size: 11px; font-weight: 700; color: #ffffff; margin-top: 4px;}
</style>
""", unsafe_allow_html=True)

conn = sqlite3.connect("mock_utility.db")
# 🌟 FIX: We now use df_all for EVERYTHING. No filtering out 'CLEAR' status.
df_all = pd.read_sql_query("SELECT * FROM triage_results WHERE status != 'INSPECTED'", conn)
conn.close()

st.markdown("""
<div style="display:flex;align-items:center;gap:15px;margin-bottom:20px;">
    <div style="width:45px;height:45px;border-radius:50%;background:linear-gradient(135deg,rgba(82,220,247,0.7),rgba(6,120,147,0.9));border:1.5px solid rgba(255,255,255,0.7);display:flex;align-items:center;justify-content:center;font-size:22px;">💧</div>
    <div><h1 class="header-title">Aquara</h1><div class="header-sub">Bringing Intelligence to Water Infrastructure</div></div>
</div>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns([1.3, 2.4, 1.5], gap="medium")

with col1:
    st.markdown('<div class="section-label">1. Data Ingestion</div>', unsafe_allow_html=True)
    uploaded_files = st.file_uploader("Upload files", accept_multiple_files=True, label_visibility="collapsed")
    
    oversized_detected = False
    if uploaded_files:
        os.makedirs("sample_data", exist_ok=True)
        for file in uploaded_files:
            if file.size > 2 * 1024: oversized_detected = True
            else:
                with open(os.path.join("sample_data", file.name), "wb") as f: f.write(file.getbuffer())
        if oversized_detected: st.error("Upload aborted: One or more files exceed 2 KB limit.")
        else: st.success(f"Staged {len(uploaded_files)} ingestion package(s).")
            
    st.markdown('<div class="section-label">2. Processing</div>', unsafe_allow_html=True)
    processing_status_box = st.empty()
    
    if st.button("▶ Run Scoring Engine"):
        if not uploaded_files or oversized_detected: st.warning("Ingestion failure: Staged dataset is missing or invalid.")
        else:
            processing_status_box.markdown("""
                <div style="background: rgba(24, 197, 232, 0.25); border: 2px solid #18c5e8; padding: 12px; border-radius: 8px; margin-bottom: 15px; text-align: center;">
                    <h5 style='color: white; margin: 0; font-weight: 700;'>⚙ ENGINE PIPELINE ACTIVE</h5>
                    <p style='color: #a0eeff; margin: 5px 0 0 0; font-size: 12px;'>Parsing telemetry logs for anomaly explanation reporting...</p>
                </div>
            """, unsafe_allow_html=True)
            with st.spinner("Executing analytical matrix..."): engine_status = run_nightly_triage()
            processing_status_box.empty()
            if engine_status and engine_status.get("status") == "unsuitable": st.error("Data Unsuitable: Structural check validation failure.")
            elif engine_status and engine_status.get("status") == "malformed_json": st.error("JSON Error: Broken syntax parsed.")
            else: st.cache_data.clear(); st.rerun()

    st.markdown('<div class="section-label">System Architecture Status</div>', unsafe_allow_html=True)
    st.markdown('<div class="status-row"><div class="dot dot-g"></div>Network: Air-Gapped Mode</div><div class="status-row"><div class="dot dot-b"></div>AI Context Provider: Live</div><div class="status-row"><div class="dot dot-g"></div>Local Cache Sync: Nominal</div>', unsafe_allow_html=True)
    
    st.markdown('<div style="font-size:11px; margin-top:8px; padding:10px; background:rgba(0,0,0,0.2); border-radius:6px; line-height:1.45; border: 1px solid rgba(255,255,255,0.15);"><strong style="color: white; font-size: 12px;">Triage Class Boundaries:</strong><br><span style="color:#ef4444; font-weight: 700;">• Critical Alert</span>: Structural score above 80%<br><span style="color:#f59e0b; font-weight: 700;">• Watch List</span>: Variance index between 50% – 80%<br><span style="color:#10b981; font-weight: 700;">• Clear Zone</span>: Metrics stable under 50% bounds</div>', unsafe_allow_html=True)

    critical_n = len(df_all[df_all['risk_score'] > 0.80]) if not df_all.empty else 0
    warn_n = len(df_all[(df_all['risk_score'] > 0.50) & (df_all['risk_score'] <= 0.80)]) if not df_all.empty else 0
    ok_n = len(df_all[df_all['risk_score'] <= 0.50]) if not df_all.empty else 0

    st.markdown('<div class="section-label">Today\'s Diagnostics Summary</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="metric"><div class="mlabel">Critical Alerts</div><div class="mval" style="color:#ffcccc;">{critical_n}</div></div><div class="metric"><div class="mlabel">Active Watches</div><div class="mval" style="color:#ffe6cc;">{warn_n}</div></div><div class="metric"><div class="mlabel">Clear Assets</div><div class="mval" style="color:#ccffcc;">{ok_n}</div></div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="section-label">High-Risk Zone Map</div>', unsafe_allow_html=True)
    m = folium.Map(location=[42.283, -71.226], zoom_start=13, tiles="CartoDB positron")
    
    # 🌟 FIX: Use df_all to render map pins for every item
    if not df_all.empty:
        for _, row in df_all.iterrows():
            if pd.isna(row['lat']) or pd.isna(row['lon']): continue
            
            # Add Blue coloring logic for Clear Zone pins
            if row['risk_score'] > 0.80: marker_color = "red"
            elif row['risk_score'] > 0.50: marker_color = "orange"
            else: marker_color = "blue"
            
            popup_html = f"<div style=\"font-family:'DM Sans',sans-serif;font-size:13px;color:#062a38;\"><strong>Asset: {row['junction_id']}</strong><br>Zone: {row['zone_id']}<br>Variance: <strong>{row['risk_score']:.0%}</strong></div>"
            folium.Marker(location=[row["lat"], row["lon"]], popup=folium.Popup(popup_html, max_width=200), tooltip=f"{row['junction_id']} ({row['risk_score']:.0%})", icon=folium.Icon(color=marker_color, icon="tint", prefix="fa")).add_to(m)
    st_folium(m, height=480, use_container_width=True)

with col3:
    st.markdown('<div class="section-label">Priority Queue</div>', unsafe_allow_html=True)
    if not df_all.empty:
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1: st.download_button(label="CSV Export", data=df_all.to_csv(index=False).encode("utf-8"), file_name="aquara_manifest.csv", mime="text/csv", use_container_width=True)
        with col_dl2: st.download_button(label="PDF Export", data=create_pdf_report(df_all), file_name="aquara_manifest.pdf", mime="application/pdf", use_container_width=True)

        # 🌟 FIX: Use df_all to render the queue, and include Variance % in the UI
        queue_df = df_all.sort_values("risk_score", ascending=False)
        for idx, row in queue_df.iterrows():
            score = row["risk_score"]
            if score > 0.80: b_class, b_txt, b_color = ("badge-r", "Critical", "#ef4444")
            elif score > 0.50: b_class, b_txt, b_color = ("badge-a", "Warning", "#f59e0b")
            else: b_class, b_txt, b_color = ("badge-g", "Clear", "#10b981")
            
            # 🌟 FIX: Added the Variance UI element here
            st.markdown(f"""
                <div class="queue-item">
                    <div class="qi-head">
                        <div class="qi-name">{row["zone_id"]} • {row["junction_id"]}</div>
                        <span class="badge {b_class}">{b_txt}</span>
                    </div>
                    <div class="qi-var">Calculated Variance: {score:.0%}</div>
                    <div class="pbar-bg"><div class="pbar" style="width:{int(score * 100)}%;background:{b_color};"></div></div>
                    <div class="qi-exp">{row["explanation"]}</div>
                    <div class="qi-code">{row["work_order"]}</div>
                </div>
            """, unsafe_allow_html=True)
            if st.button("Mark Inspected", key=f"btn_inspect_{idx}_{row['junction_id']}"):
                conn = sqlite3.connect("mock_utility.db")
                conn.execute("UPDATE triage_results SET status = 'INSPECTED' WHERE junction_id = ?", (row["junction_id"],))
                conn.commit(); conn.close(); st.cache_data.clear(); st.rerun()
    else:
        st.markdown('<div class="queue-item" style="text-align:center;font-size:13px;padding:25px;font-weight:600;">Queue is currently empty.<br><br>Stage operational datasets to continue triage tracking.</div>', unsafe_allow_html=True)