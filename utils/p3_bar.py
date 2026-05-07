"""P3 Tab — Biểu đồ phân rã dòng tiền (multi-panel by ma_don_vi)."""
from __future__ import annotations

import pandas as pd
from plotly.subplots import make_subplots
import streamlit as st

from utils.breakdown_chart import (
    add_breakdown_panel,
    compute_label_y_offset,
    compute_periods,
    resolve_breakdown,
)
from utils.p3_filter_controls import (
    apply_breakdown_filters,
    render_breakdown_filters,
)
from utils.ui import chart_height_slider

_N_PER_ROW = 3
# TODO: thay bằng companies.csv type=HOLDING/SUB_HOLDING khi wire xong (Phase D)
_DEFAULT_PANEL_UNITS = ["GELEX", "GEE", "GEL"]


def render(
    *,
    df_report: pd.DataFrame,
    base: pd.DataFrame,
    ordered_labels: list[str],
    label_to_unit: dict[str, str],
) -> None:
    """Render Bar tab in-place. Mỗi đơn vị được chọn = 1 panel chart riêng."""
    report_units = set(df_report["ma_don_vi"].dropna().unique())
    default_units = [u for u in _DEFAULT_PANEL_UNITS if u in report_units]

    state = render_breakdown_filters(
        prefix="p3_bar",
        base=base,
        ordered_labels=ordered_labels,
        label_to_unit=label_to_unit,
        default_units=default_units,
        units_label="Đơn vị (mỗi đơn vị = 1 chart)",
        with_yaxis=True,
    )

    if not state.units:
        st.info('Chọn ít nhất một đơn vị ở ô "Đơn vị" để hiển thị biểu đồ.')
        return

    bar, km_filter = apply_breakdown_filters(base, state)
    if bar.empty:
        st.info("Không có dữ liệu với bộ lọc hiện tại.")
        return

    bar, periods_sorted, x_numeric = compute_periods(bar, state.period_mode)
    is_breakdown, stack_col, cat_list, opacity_map = resolve_breakdown(
        state.breakdown, bar
    )

    # ── Build figure ────────────────────────────────────────────────────────
    n_panels = len(state.units)
    n_rows = (n_panels + _N_PER_ROW - 1) // _N_PER_ROW
    titles = state.units + [""] * (n_rows * _N_PER_ROW - n_panels)

    fig = make_subplots(
        rows=n_rows, cols=_N_PER_ROW,
        shared_yaxes=(state.yaxis_mode == "Chung"),
        subplot_titles=titles,
        horizontal_spacing=0.08,
        vertical_spacing=0.18 if n_rows > 1 else 0.0,
    )

    shown_legend: set = set()
    for idx, unit_code in enumerate(state.units):
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
    if state.yaxis_mode == "Chung":
        for r in range(1, n_rows + 1):
            fig.update_yaxes(
                title_text="triệu VNĐ", title_font=dict(size=10), row=r, col=1,
            )
    else:
        fig.update_yaxes(title_text="triệu VNĐ", title_font=dict(size=10))
    st.plotly_chart(fig, use_container_width=True, key="p3_bar_chart")
