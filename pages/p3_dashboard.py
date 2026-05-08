"""P3 — Dashboard chiến lược.

Orchestrator: load data, apply global filters, dispatch to per-tab modules
in `utils/p3_*.py`.
"""
import streamlit as st

from utils.data_loader import load_data
from utils.filters import (
    apply_global_filters,
    build_unit_label_list,
    get_global_filters,
    unit_group_map,
)
from utils.p3_bar import render as render_bar
from utils.p3_cumul import render as render_cumul
from utils.p3_heatmap import render as render_heatmap
from utils.p3_pivot import render as render_pivot
from utils.p3_sankey import render as render_sankey
from utils.p3_sankey_echarts import render as render_sankey_ec
from utils.p3_total import render as render_total

st.header("Dashboard chiến lược")

with st.spinner("Đang tải dữ liệu..."):
    data = load_data()

df_report = data["report"]
df_summary = data["summary"]

nam_list, quy_list, nhom = get_global_filters()
unit_group = unit_group_map(df_summary)

# Page-level base = df_report đã filter NĂM/QUÝ/NHÓM toàn cục
base = apply_global_filters(df_report, nam_list, quy_list)
base["group"] = base["ma_don_vi"].map(unit_group)
if nhom != "Tất cả":
    base = base[base["group"] == nhom]

ordered_labels, label_to_unit = build_unit_label_list(
    df_summary, units=set(base["ma_don_vi"].dropna().unique())
)

(
    tab_sankey, tab_sankey_ec, tab_heatmap, tab_pivot,
    tab_bar, tab_total, tab_cumul,
) = st.tabs([
    "Sankey (Plotly)",
    "Sankey (ECharts)",
    "Heatmap Dòng tiền từng CT",
    "Bảng pivot",
    "Biểu đồ phân rã dòng tiền",
    "Tổng hợp dòng tiền",
    "Tích lũy dư tiền",
])

with tab_sankey:
    render_sankey(
        df_report=df_report, nam_list=nam_list, quy_list=quy_list,
        nhom=nhom, unit_group=unit_group,
        ordered_labels=ordered_labels, label_to_unit=label_to_unit,
    )

with tab_sankey_ec:
    render_sankey_ec(
        df_report=df_report, nam_list=nam_list, quy_list=quy_list,
        nhom=nhom, unit_group=unit_group,
        ordered_labels=ordered_labels, label_to_unit=label_to_unit,
    )

with tab_heatmap:
    render_heatmap(
        base=base, ordered_labels=ordered_labels, label_to_unit=label_to_unit,
    )

with tab_pivot:
    render_pivot(
        base=base, ordered_labels=ordered_labels, label_to_unit=label_to_unit,
    )

with tab_bar:
    render_bar(
        df_report=df_report, base=base,
        ordered_labels=ordered_labels, label_to_unit=label_to_unit,
        unit_group=unit_group,
    )

with tab_total:
    render_total(
        df_report=df_report, base=base,
        ordered_labels=ordered_labels, label_to_unit=label_to_unit,
    )

with tab_cumul:
    render_cumul()
