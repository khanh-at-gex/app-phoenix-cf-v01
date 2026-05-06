import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

# On Streamlit Cloud there is no .env; bridge st.secrets → os.environ
for _k, _v in st.secrets.items():
    if isinstance(_v, str):
        os.environ.setdefault(_k, _v)

from utils.sidebar import init_session_state, render_sidebar

st.set_page_config(
    page_title="GELEX · CASHPLAN",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Password gate ─────────────────────────────────────────────────────────────
_APP_PASSWORD = os.environ.get("APP_PASSWORD", "").strip()

if _APP_PASSWORD and not st.session_state.get("authenticated"):
    st.title("GELEX · CASHPLAN")
    pwd = st.text_input("Mật khẩu", type="password")
    if st.button("Đăng nhập"):
        if pwd == _APP_PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Mật khẩu không đúng.")
    st.stop()

# ── App ───────────────────────────────────────────────────────────────────────
init_session_state()

with st.sidebar:
    st.markdown("## GELEX · CASHPLAN")
    st.markdown("---")

pages = [
    st.Page("pages/p2_tracking.py", title="Theo dõi dữ liệu", icon="📋"),
    st.Page("pages/p3_dashboard.py", title="Dashboard chiến lược", icon="📊"),
    st.Page("pages/p4_detail.py", title="Chi tiết CTTV", icon="🏢"),
    st.Page("pages/p5_adl.py", title="Ma trận ADL", icon="🎯"),
]

pg = st.navigation(pages)
render_sidebar()
pg.run()
