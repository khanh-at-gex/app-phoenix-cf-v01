"""P3 Tab — Biểu đồ phân rã dòng tiền (multi-panel by ma_don_vi)."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
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
from utils.ui import chart_font_scale, chart_height_slider

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

    bar_font_scale = chart_font_scale("p3_bar_font")

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
            font_scale=bar_font_scale,
        )

        # ── Line "Tổng CF" (sum CFO+CFI+CFF per period) ───────────────────
        total_series = (
            g_df[g_df["khoan_muc"].isin(km_filter)]
            .groupby("_period")["so_tien_tong"].sum()
            .reindex(periods_sorted, fill_value=0)
        )
        fig.add_trace(
            go.Scatter(
                x=x_numeric, y=total_series.values,
                name="Tổng CF",
                mode="lines+markers",
                line=dict(color="#e67e22", width=2.5, dash="dot"),
                marker=dict(size=8, color="#e67e22"),
                legendgroup="Tổng CF",
                showlegend=(idx == 0),  # show legend chỉ panel đầu
                customdata=periods_sorted,
                hovertemplate=(
                    f"<b>Tổng CF — {unit_code}</b><br>%{{customdata}}<br>"
                    "%{y:,.0f} triệu<extra></extra>"
                ),
            ),
            row=row, col=col,
        )

    bar_height = chart_height_slider(
        "p3_bar_height",
        default=max(420, n_rows * 380 + 80),
        min_v=400, max_v=800, step=50,
    )
    base_font = max(8, int(11 * bar_font_scale))
    axis_title_font = max(7, int(10 * bar_font_scale))
    fig.update_layout(
        barmode="stack",
        legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="left", x=0),
        height=bar_height,
        margin=dict(l=0, r=0, t=80, b=40),
        font=dict(size=base_font),
    )
    fig.update_xaxes(
        tickmode="array", tickvals=x_numeric,
        ticktext=periods_sorted, tickangle=-45,
        tickfont=dict(size=base_font),
    )
    if state.yaxis_mode == "Chung":
        for r in range(1, n_rows + 1):
            fig.update_yaxes(
                title_text="triệu VNĐ", title_font=dict(size=axis_title_font),
                tickfont=dict(size=base_font), row=r, col=1,
            )
    else:
        fig.update_yaxes(
            title_text="triệu VNĐ", title_font=dict(size=axis_title_font),
            tickfont=dict(size=base_font),
        )
    st.plotly_chart(fig, use_container_width=True, key="p3_bar_chart")
