"""P6 — Mô phỏng (Manual sensitivity)."""
import streamlit as st

from utils.data_loader import load_data
from utils.qtrr_sim.manual import render

st.header("Mô phỏng dòng tiền")

with st.spinner("Đang tải dữ liệu..."):
    data = load_data()

render(
    df_report=data["report"],
    df_key_drivers=data["key_drivers"],
    df_summary=data["summary"],
)
