import streamlit as st
from utils.sidebar import init_session_state, render_sidebar

st.set_page_config(
    page_title="GELEX · CASHPLAN",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session_state()

st.markdown("""
<style>
[data-testid="stSidebarNav"]::before {
    content: "PHOENIX: CASHPLAN Dashboard";
    display: block;
    font-size: 1.4rem;
    font-weight: 700;
    color: Red;
    padding: 1.2rem 1rem 0.8rem 1rem;
    border-bottom: 1px solid rgba(255,255,255,0.2);
    margin-bottom: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

pages = [
    st.Page("pages/p2_tracking.py", title="Theo dõi dữ liệu", icon="📋"),
    st.Page("pages/p3_dashboard.py", title="Dashboard chiến lược", icon="📊"),
    st.Page("pages/p4_detail.py", title="Chi tiết CTTV", icon="🏢"),
    st.Page("pages/p5_adl.py", title="Ma trận ADL", icon="🎯"),
]

pg = st.navigation(pages)
render_sidebar()
pg.run()
