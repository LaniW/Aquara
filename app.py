import sys
import os
import sqlite3
import pandas as pd
import folium
from streamlit_folium import st_folium
import streamlit as st

# Ensure Python can find the 'api' folder regardless of terminal location
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from api.main import run_nightly_triage

# ── PDF GENERATOR ───────────────────────────────────────────────────────────────
def create_pdf_report(dataframe):
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("helvetica", style="B", size=18)
        pdf.cell(0, 10, "Aquara Leak Triage Report", ln=True, align='C')
        pdf.ln(5)
        
        for idx, row in dataframe.iterrows():
            pdf.set_font("helvetica", style='B', size=12)
            pdf.cell(0, 8, f"Zone: {row['zone_id']} | Asset: {row['junction_id']} | Risk: {row['risk_score']:.0%}", ln=True)
            pdf.set_font("helvetica", size=10)
            pdf.multi_cell(0, 6, f"AI Explanation: {row['explanation']}")
            pdf.multi_cell(0, 6, f"Work Order: {row['work_order']}")
            pdf.ln(5)
            
        res = pdf.output(dest='S')
        return res.encode('latin-1') if isinstance(res, str) else bytes(res)
    except Exception as e:
        return f"Error generating PDF. Please ensure fpdf2 is installed: pip install fpdf2\n\n{str(e)}".encode('utf-8')

# ── PAGE CONFIG ─────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Aquara", page_icon="💧", layout="wide", initial_sidebar_state="collapsed")

# ── CSS REFINEMENT (HIGH CONTRAST & TYPOGRAPHY) ─────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,700&family=Space+Grotesk:wght@300;400;700&display=swap');

/* Base Application Background */
.stApp {
    font-family: 'DM Sans', sans-serif !important;
    background: linear-gradient(175deg, #069ab8 0%, #083040 55%, #041e2a 100%) !important;
    color: white !important;
}

/* Hide Streamlit Default Chrome */
#MainMenu, footer, header {visibility: hidden !important; display: none !important;}
.block-container {padding: 1rem 2rem 2rem !important; z-index: 2;}

/* Glass Panels */
[data-testid="column"] > div {
    background: rgba(240, 253, 255, 0.28) !important;
    backdrop-filter: blur(20px) saturate(160%) !important;
    -webkit-backdrop-filter: blur(20px) saturate(160%) !important;
    border: 1px solid rgba(255, 255, 255, 0.65) !important;
    border-top: 2px solid rgba(255, 255, 255, 0.88) !important;
    border-radius: 14px !important;
    padding: 15px !important;
    box-shadow: inset 0 2px 0 rgba(255, 255, 255, 0.65), 0 10px 30px rgba(6, 120, 147, 0.2) !important;
    height: 100%;
}

/* 🌟 HIGH CONTRAST TYPOGRAPHY 🌟 */
.header-title { 
    font-family: 'DM Sans', sans-serif; font-size: 28px; font-weight: 700; color: #ffffff; 
    text-transform: uppercase; letter-spacing: 0.05em; text-shadow: 0 2px 14px rgba(6,154,184,0.8); margin: 0;
}
.header-sub { font-size: 13px; font-weight: 500; color: #ffffff; letter-spacing: 0.05em; margin-top: 2px; }

.section-label { 
    font-family: 'DM Sans', sans-serif !important; font-size: 15px; font-weight: 700; 
    letter-spacing: 0.1em; text-transform: uppercase; color: #ffffff !important; 
    border-bottom: 2px solid rgba(255,255,255,0.4); padding-bottom: 6px; margin-bottom: 12px; margin-top: 10px;
    text-shadow: 0 2px 4px rgba(0,0,0,0.8), 0 0 10px rgba(82,220,247,0.5);
}

/* Metrics (Critical / Watch List) */
.metric { 
    background: rgba(220,248,255,0.42); border: 1px solid rgba(152,236,255,0.35); 
    border-top: 1.5px solid rgba(255,255,255,0.75); border-radius: 9px; padding: 8px 10px; 
    margin-bottom: 6px; display: flex; justify-content: space-between; align-items: center;
}
.mlabel { font-size: 13px; font-weight: 700; letter-spacing: 0.07em; text-transform: uppercase; color: #ffffff; text-shadow: 0 1px 3px rgba(0,0,0,0.9);}
.mval { font-family: 'DM Sans', sans-serif; font-size: 20px; font-weight: 700; text-shadow: 0 1px 2px rgba(0,0,0,0.5);}

/* Buttons */
.stButton > button {
    width: 100% !important; font-size: 13px !important; font-weight: 700 !important; text-transform: uppercase !important;
    color: #083040 !important; border-radius: 7px !important; padding: 6px !important;
    border: 1px solid rgba(6,154,184,0.35) !important; border-top: 1.5px solid rgba(255,255,255,0.95) !important;
    background: linear-gradient(175deg, rgba(255,255,255,0.92) 0%, rgba(207,248,255,0.85) 40%, rgba(155,238,255,0.8) 55%, rgba(207,248,255,0.88) 100%) !important;
    box-shadow: inset 0 1.5px 0 rgba(255,255,255,0.95), 0 2px 6px rgba(6,120,147,0.12) !important;
    font-family: 'DM Sans', sans-serif !important; letter-spacing: 0.05em;
}
.stDownloadButton > button {
    background: linear-gradient(175deg, rgba(255,255,255,0.92) 0%, rgba(209,250,229,0.88) 40%, rgba(167,243,208,0.82) 55%, rgba(209,250,229,0.9) 100%) !important;
    border-color: rgba(16,185,129,0.35) !important; color: #033d1c !important; width: 100%; text-transform: uppercase !important; font-weight: 700 !important;
}

/* Functional File Uploader Styling */
[data-testid="stFileUploadDropzone"] {
    border: 1.5px dashed rgba(255,255,255,0.6) !important; 
    border-radius: 8px !important; background: rgba(240,253,255,0.25) !important; 
    padding: 12px 6px !important; text-align: center !important; margin-bottom: 10px !important; 
}
[data-testid="stFileUploadDropzone"]:hover {
    background: rgba(240,253,255,0.45) !important; border-color: #ffffff !important;
}
[data-testid="stFileUploadDropzone"] > div > span { color: #ffffff !important; font-size: 14px !important; font-weight: 700 !important; text-shadow: 0 1px 3px rgba(0,0,0,0.7) !important;}
[data-testid="stFileUploadDropzone"] svg { fill: #ffffff !important; }

/* Status Rows */
.status-row { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #ffffff; padding: 4px 0; font-weight: 700; text-shadow: 0 1px 3px rgba(0,0,0,0.8);}
.dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.dot-g { background: #10b981; box-shadow: 0 0 6px rgba(16,185,129,0.6); }
.dot-b { background: #18c5e8; box-shadow: 0 0 6px rgba(24,197,232,0.6); }

/* Queue Items */
.queue-item { background: rgba(240,253,255,0.40); border: 1px solid rgba(152,236,255,0.35); border-radius: 9px; padding: 10px; margin-bottom: 10px; }
.qi-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.qi-name { font-size: 14px; font-weight: 700; color: #062a38; }
.badge { font-size: 9px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; padding: 3px 8px; border-radius: 999px; border: 1px solid; }
.badge-r { background: rgba(239,68,68,0.2); border-color: rgba(239,68,68,0.8); color: #7f1d1d; }
.badge-a { background: rgba(251,191,36,0.2); border-color: rgba(251,191,36,0.8); color: #713f12; }
.badge-g { background: rgba(16,185,129,0.2); border-color: rgba(16,185,129,0.6); color: #064e3b; }
.pbar-bg { background: rgba(6,120,147,0.12); border-radius: 999px; height: 5px; margin: 6px 0 8px; overflow: hidden; }
.pbar { height: 100%; border-radius: 999px; }
.qi-exp { font-size: 11px; color: #0e4d61; font-weight: 600; line-height: 1.4; background: rgba(207,248,255,0.5); border-radius: 6px; padding: 6px 8px; margin-bottom: 6px; }
.qi-code { font-size: 11px; font-weight: 600; color: #2a7b95; background: rgba(8,48,64,0.85); border-radius: 5px; padding: 6px; font-family: monospace; margin-bottom: 8px;}
</style>
""", unsafe_allow_html=True)

# ── DATA LOADING ────────────────────────────────────────────────────────────────
@st.cache_data
def load_local_data() -> pd.DataFrame:
    try:
        conn = sqlite3.connect("mock_utility.db")
        # STRICTLY pull only items that have NOT been inspected
        df = pd.read_sql_query("SELECT * FROM triage_results WHERE status != 'INSPECTED'", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame(columns=["junction_id", "zone_id", "risk_score", "lat", "lon", "explanation", "work_order", "status"])

df = load_local_data()

# ── HEADER ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="display:flex;align-items:center;gap:15px;margin-bottom:20px;z-index:2;position:relative;">
    <div style="width:45px;height:45px;border-radius:50%;background:linear-gradient(135deg,rgba(82,220,247,0.7),rgba(6,120,147,0.9));border:1.5px solid rgba(255,255,255,0.7);box-shadow:0 3px 12px rgba(6,154,184,0.4);display:flex;align-items:center;justify-content:center;font-size:22px;">💧</div>
    <div>
        <h1 class="header-title">Aquara Triage</h1>
        <div class="header-sub">Bringing Intelligence to Water Infrastructure</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── COLUMNS ─────────────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns([1.2, 2.5, 1.5], gap="medium")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COLUMN 1: INGESTION & STATUS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with col1:
    st.markdown('<div class="section-label">1. Data Ingestion</div>', unsafe_allow_html=True)
    
    uploaded_files = st.file_uploader(
        "Upload files", 
        accept_multiple_files=True, 
        label_visibility="collapsed"
    )
    
    if uploaded_files:
        os.makedirs("sample_data", exist_ok=True)
        for file in uploaded_files:
            with open(os.path.join("sample_data", file.name), "wb") as f:
                f.write(file.getbuffer())
        st.success(f"Files staged. Ready to run.")
    
    st.markdown('<div class="section-label">2. Processing</div>', unsafe_allow_html=True)
    if st.button("▶ Run Scoring Engine"):
        with st.spinner("Analyzing files with Gemini..."):
            run_nightly_triage()
        st.cache_data.clear() # Clear cache to fetch new DB rows immediately
        st.rerun()

    st.markdown('<div class="section-label">System Status</div>', unsafe_allow_html=True)
    st.markdown("""
        <div class="status-row"><div class="dot dot-g"></div>Network: Air-Gapped</div>
        <div class="status-row"><div class="dot dot-b"></div>AI Explainer: Online</div>
        <div class="status-row"><div class="dot dot-g"></div>Database: Synced</div>
    """, unsafe_allow_html=True)

    critical_n = len(df[df['risk_score'] > 0.80]) if not df.empty else 0
    warn_n = len(df[(df['risk_score'] > 0.50) & (df['risk_score'] <= 0.80)]) if not df.empty else 0
    ok_n = len(df[df['risk_score'] <= 0.50]) if not df.empty else 0

    st.markdown('<div class="section-label">Today\'s Summary</div>', unsafe_allow_html=True)
    st.markdown(f"""
        <div class="metric"><div class="mlabel">Critical</div><div class="mval" style="color:#ffcccc;">{critical_n}</div></div>
        <div class="metric"><div class="mlabel">Watch List</div><div class="mval" style="color:#ffe6cc;">{warn_n}</div></div>
        <div class="metric"><div class="mlabel">Clear Zones</div><div class="mval" style="color:#ccffcc;">{ok_n}</div></div>
    """, unsafe_allow_html=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COLUMN 2: LEAFLET MAP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with col2:
    st.markdown('<div class="section-label">High-Risk Zone Map</div>', unsafe_allow_html=True)
    
    m = folium.Map(location=[42.283, -71.226], zoom_start=13, tiles="CartoDB positron")

    if not df.empty:
        for _, row in df.iterrows():
            # SAFETY CHECK: Only plot if coordinates are valid
            if pd.isna(row['lat']) or pd.isna(row['lon']): continue
            
            # 🌟 FIX: Initialize color to a default, then update based on logic
            color = "blue" 
            if row['risk_score'] > 0.8: 
                color = "red"
            elif row['risk_score'] > 0.5: 
                color = "orange"
            
            popup_html = f"""<div style="font-family:'DM Sans',sans-serif;font-size:14px;color:#062a38;">
                <strong>{row['junction_id']}</strong><br>
                Zone: {row['zone_id']}<br>
                Risk: <strong>{row['risk_score']:.0%}</strong>
            </div>"""
            
            folium.Marker(
                location=[row["lat"], row["lon"]],
                popup=folium.Popup(popup_html, max_width=200),
                tooltip=f"{row['junction_id']} ({row['risk_score']:.0%})",
                icon=folium.Icon(color=color, icon="tint", prefix="fa"),
            ).add_to(m)

    st_folium(m, height=450, use_container_width=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COLUMN 3: PRIORITY QUEUE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COLUMN 3: PRIORITY QUEUE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with col3:
    st.markdown('<div class="section-label">Priority Queue</div>', unsafe_allow_html=True)

    if not df.empty:
        # Create a container for the buttons to keep them aligned
        btn_col1, btn_col2 = st.columns(2)
        
        csv_data = df[["zone_id", "junction_id", "risk_score", "work_order"]].to_csv(index=False).encode("utf-8")
        pdf_data = create_pdf_report(df)
        
        with btn_col1:
            st.download_button(label="CSV", data=csv_data, file_name="aquara_queue.csv", mime="text/csv", use_container_width=True)
        with btn_col2:
            st.download_button(label="PDF", data=pdf_data, file_name="aquara_queue.pdf", mime="application/pdf", use_container_width=True)

    if not df.empty:
        queue_df = df.sort_values("risk_score", ascending=False)
        for idx, row in queue_df.iterrows():
            score = row["risk_score"]
            bar_w = int(score * 100)
            
            # Simplified labels without emojis
            if score > 0.80:
                badge_class, badge_txt, bar_c = "badge-r", "Critical", "#ef4444"
            elif score > 0.50:
                badge_class, badge_txt, bar_c = "badge-a", "Warning", "#f59e0b"
            else:
                badge_class, badge_txt, bar_c = "badge-g", "Clear", "#10b981"

            st.markdown(f"""
                <div class="queue-item">
                    <div class="qi-head">
                        <div class="qi-name">{row['zone_id']} · {row['junction_id']}</div>
                        <span class="badge {badge_class}">{badge_txt}</span>
                    </div>
                    <div class="pbar-bg"><div class="pbar" style="width:{bar_w}%;background:{bar_c};"></div></div>
                    <div class="qi-exp">{row['explanation']}</div>
                    <div class="qi-code">{row['work_order']}</div>
                </div>
            """, unsafe_allow_html=True)
            
            if st.button("Mark Inspected", key=f"btn_inspect_{idx}"):
                conn = sqlite3.connect("mock_utility.db")
                conn.execute("UPDATE triage_results SET status = 'INSPECTED' WHERE junction_id = ?", (row["junction_id"],))
                conn.commit()
                conn.close()
                st.cache_data.clear()
                st.rerun()
    else:
        st.markdown("""<div class="queue-item" style="text-align:center;color:#ffffff;font-size:13px;padding:20px;font-weight:600;">Queue is empty.</div>""", unsafe_allow_html=True)