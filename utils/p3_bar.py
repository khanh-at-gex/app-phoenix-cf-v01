"""P3 Tab 3 — Biểu đồ phân rã dòng tiền (multi-panel by ma_don_vi)."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from utils.breakdown_chart import (
    BREAKDOWN_OPTIONS,
    add_breakdown_panel,
    compute_label_y_offset,
    compute_periods,
    resolve_breakdown,
)
from utils.ui import chart_height_slider

_N_PER_ROW = 3
_DEFAULT_PANEL_UNITS = ["GELEX", "GEE", "GEL"]


def render(
    *,
    df_report: pd.DataFrame,
    base: pd.DataFrame,
    ordered_labels: list[str],
    label_to_unit: dict[str, str],
) -> None:
    """Render Bar tab in-place."""
    # ── Chart options row ──────────────────────────────────────────────────
    st.caption("Tùy chọn biểu đồ")
    g1, g2, g3 = st.columns([3, 2, 2])
    with g1:
        bar_stack = st.segmented_control(
            "Cách phân rã theo", BREAKDOWN_OPTIONS,
            default="Không phân rã", key="p3_bar_stack",
        ) or "Không phân rã"
    with g2:
        bar_period = st.segmented_control(
            "Kỳ", ["Năm", "Quý"], default="Năm", key="p3_bar_period",
        ) or "Năm"
    with g3:
        bar_yaxis = st.segmented_control(
            "Trục Y", ["Riêng", "Chung"], default="Riêng", key="p3_bar_yaxis",
        ) or "Riêng"

    # ── Data filter row ────────────────────────────────────────────────────
    st.caption("Bộ lọc dữ liệu")
    f1, f2, f3, f4, f5 = st.columns([3, 2, 2, 2, 3])
    with f1:
        # Default panels: HOLDING + SUB_HOLDING (consolidated files)
        # TODO: thay bằng companies.csv type lookup khi wire xong
        report_units = set(df_report["ma_don_vi"].dropna().unique())
        default_units = [u for u in _DEFAULT_PANEL_UNITS if u in report_units]
        default_labels = [
            lb for lb in ordered_labels if label_to_unit[lb] in default_units
        ]
        bar_unit_labels = st.multiselect(
            "Đơn vị (mỗi đơn vị = 1 chart)",
            ordered_labels, default=default_labels, key="p3_bar_units",
        )
        bar_units = [label_to_unit[lb] for lb in bar_unit_labels]
    with f2:
        bar_km = st.segmented_control(
            "Khoản mục", ["Tất cả", "CFO", "CFI", "CFF"],
            default="Tất cả", key="p3_bar_km",
        ) or "Tất cả"
    with f3:
        bar_on_dinh = st.segmented_control(
            "Phân loại ổn định", ["Tất cả", "Ổn định", "Không ổn định"],
            default="Tất cả", key="p3_bar_on_dinh",
        ) or "Tất cả"
    with f4:
        bar_noi_ngoai = st.segmented_control(
            "Phân loại Nội/Ngoại", ["Tất cả", "Bên trong", "Bên ngoài"],
            default="Tất cả", key="p3_bar_noi_ngoai",
        ) or "Tất cả"

    # Loại giao dịch options phụ thuộc vào Khoản mục đang chọn
    if bar_km != "Tất cả":
        ct_scope = base[base["khoan_muc"] == bar_km]
    else:
        ct_scope = base[base["khoan_muc"].isin(["CFO", "CFI", "CFF"])]
    ct_opts = sorted(ct_scope["chi_tieu"].dropna().unique().tolist())

    with f5:
        bar_chi_tieu = st.selectbox(
            "Loại giao dịch", ["Tất cả"] + ct_opts, key="p3_bar_chi_tieu",
        )

    # ── Apply filters ───────────────────────────────────────────────────────
    bar = base.copy()
    if bar_km != "Tất cả":
        bar = bar[bar["khoan_muc"] == bar_km]
        km_filter = [bar_km]
    else:
        bar = bar[bar["khoan_muc"].isin(["CFO", "CFI", "CFF"])]
        km_filter = ["CFO", "CFI", "CFF"]
    if bar_on_dinh != "Tất cả":
        bar = bar[bar["phan_loai_on_dinh_khong_on_dinh"] == bar_on_dinh]
    if bar_noi_ngoai != "Tất cả":
        bar = bar[bar["phan_loai_ben_trong_ben_ngoai"] == bar_noi_ngoai]
    if bar_chi_tieu != "Tất cả":
        bar = bar[bar["chi_tieu"] == bar_chi_tieu]

    # Period mode
    if bar_period == "Quý":
        bar = bar[bar["quy"].notna()].copy()
    bar, periods_sorted, x_numeric = compute_periods(bar, bar_period)

    if not bar_units:
        st.info('Chọn ít nhất một đơn vị ở ô "Đơn vị" để hiển thị biểu đồ.')
        return
    if bar.empty:
        st.info("Không có dữ liệu với bộ lọc hiện tại.")
        return

    is_breakdown, stack_col, cat_list, opacity_map = resolve_breakdown(bar_stack, bar)

    # ── Build figure ────────────────────────────────────────────────────────
    n_panels = len(bar_units)
    n_rows = (n_panels + _N_PER_ROW - 1) // _N_PER_ROW
    titles = bar_units + [""] * (n_rows * _N_PER_ROW - n_panels)

    fig = make_subplots(
        rows=n_rows, cols=_N_PER_ROW,
        shared_yaxes=(bar_yaxis == "Chung"),
        subplot_titles=titles,
        horizontal_spacing=0.08,
        vertical_spacing=0.18 if n_rows > 1 else 0.0,
    )

    shown_legend: set = set()
    for idx, unit_code in enumerate(bar_units):
        row = idx // _N_PER_ROW + 1
        col = idx % _N_PER_ROW + 1
        g_df = bar[bar["ma_don_vi"] == unit_code]

        label_y_offset = compute_label_y_offset(
            g_df, is_breakdown, stack_col, cat_list, km_filter,
        )
        add_breakdown_panel(
            fig, g_df,
            panel_label=unit_code,
            periods_sorted=periods_sorted, x_numeric=x_numeric,
            is_breakdown=is_breakdown, stack_col=stack_col,
            cat_list=cat_list, opacity_map=opacity_map,
            label_y_offset=label_y_offset,
            km_filter=km_filter, shown_legend=shown_legend,
            row=row, col=col,
        )

    bar_height = chart_height_slider(
        "p3_bar_height",
        default=max(420, n_rows * 380 + 80),
        min_v=400, max_v=800, step=50,
    )
    fig.update_layout(
        barmode="stack",
        legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="left", x=0),
        height=bar_height,
        margin=dict(l=0, r=0, t=80, b=40),
        font=dict(size=11),
    )
    fig.update_xaxes(
        tickmode="array", tickvals=x_numeric,
        ticktext=periods_sorted, tickangle=-45,
    )
    if bar_yaxis == "Chung":
        for r in range(1, n_rows + 1):
            fig.update_yaxes(
                title_text="triệu VNĐ", title_font=dict(size=10), row=r, col=1,
            )
    else:
        fig.update_yaxes(title_text="triệu VNĐ", title_font=dict(size=10))
    st.plotly_chart(fig, use_container_width=True, key="p3_bar_chart")
