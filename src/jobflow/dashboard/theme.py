"""可迁移的 Dashboard 主题变量与样式。"""

import streamlit as st


def inject_theme() -> None:
    st.markdown(
        """
        <style>
        :root { --jf-blue:#1677c8; --jf-ink:#182433; --jf-muted:#64748b; --jf-line:#d9e1ea; --jf-bg:#eef2f6; }
        .stApp { background:var(--jf-bg); color:#1f2937; }
        .stApp p, .stApp label, .stApp span { color:#1f2937; }
        .stCaption, [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * { color:#64748b !important; }
        [data-baseweb="tab-list"] [data-baseweb="tab"] { color:#475569 !important; }
        [data-baseweb="tab-list"] [aria-selected="true"] { color:var(--jf-blue) !important; }
        [data-testid="stTextInput"] label, [data-testid="stDateInput"] label { color:#334155 !important; }
        [data-testid="stMarkdownContainer"] small { color:#64748b !important; }
        [data-testid="stHeader"] { background:rgba(238,242,246,.92); }
        [data-testid="stSidebar"] { background:var(--jf-ink); }
        [data-testid="stSidebar"] *, [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span, [data-testid="stSidebar"] div { color:#d6e0ea !important; }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 { color:#fff !important; }
        [data-testid="stTextInput"] input, [data-testid="stDateInput"] input {
            background:#fff !important; color:#172033 !important; border:1px solid #cbd5e1 !important;
        }
        [data-testid="stTextInput"] svg, [data-testid="stDateInput"] svg { color:#64748b !important; }
        .stButton > button { background:#1677c8 !important; color:#fff !important; border:0 !important; }
        .stButton > button:hover { background:#125fa0 !important; color:#fff !important; }
        .stButton > button:disabled { background:#cbd5e1 !important; color:#64748b !important; }
        [data-testid="stMetric"] { background:#fff; border:1px solid var(--jf-line); border-radius:4px; padding:12px; }
        [data-testid="stMetricLabel"] { color:var(--jf-muted); }
        [data-testid="stMetricValue"] { color:#172033; }
        .jf-panel { background:#fff; border:1px solid var(--jf-line); border-radius:4px; padding:16px; margin:10px 0; }
        .jf-kicker { color:var(--jf-muted); font-size:12px; margin-bottom:8px; }
        .jf-status { display:inline-block; border-radius:12px; padding:3px 8px; font-size:12px; background:#dcfce7; color:#15803d; }
        .jf-status.observe { background:#fef3c7; color:#a16207; }
        .jf-status.error { background:#fee2e2; color:#b91c1c; }
        .jf-row { border-bottom:1px solid #edf1f5; padding:9px 0; }
        </style>
        """,
        unsafe_allow_html=True,
    )
