"""P3 Tab — Tổng hợp dòng tiền (single panel, sum across selected units)."""
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


def render(
    *,
    df_report: pd.DataFrame,
    base: pd.DataFrame,
    ordered_labels: list[str],
    label_to_unit: dict[str, str],
) -> None:
    """Single-panel breakdown chart cho TỔNG các đơn vị được chọn."""
    state = render_breakdown_filters(
        prefix="p3_total",
        base=base,
        ordered_labels=ordered_labels,
        label_to_unit=label_to_unit,
        default_units=None,
        units_label="Đơn vị (sum across)",
        with_cumul=True,
    )

    if not state.units:
        st.info('Chọn ít nhất một đơn vị ở ô "Đơn vị" để hiển thị biểu đồ.')
        return

    # Filter base by selected units (sum across)
    df = base[base["ma_don_vi"].isin(state.units)]
    df, km_filter = apply_breakdown_filters(df, state)
    if df.empty:
        st.info("Không có dữ liệu với bộ lọc hiện tại.")
        return

    df, periods_sorted, x_numeric = compute_periods(df, state.period_mode)
    is_breakdown, stack_col, cat_list, opacity_map = resolve_breakdown(
        state.breakdown, df
    )
    label_y_offset = compute_label_y_offset(
        df, is_breakdown, stack_col, cat_list, km_filter,
    )

    # ── Build figure with optional secondary y-axis cho lũy kế ─────────────
    fig = make_subplots(specs=[[{"secondary_y": state.show_cumul}]])

    panel_label = (
        f"Tổng hợp ({len(state.units)} đơn vị)"
        if len(state.units) > 1 else state.units[0]
    )
    total_font_scale = chart_font_scale("p3_total_font")
    shown_legend: set = set()
    add_breakdown_panel(
        fig, df,
        panel_label=panel_label,
        periods_sorted=periods_sorted, x_numeric=x_numeric,
        is_breakdown=is_breakdown, stack_col=stack_col,
        cat_list=cat_list, opacity_map=opacity_map,
        label_y_offset=label_y_offset,
        km_filter=km_filter, shown_legend=shown_legend,
        row=1, col=1,
        font_scale=total_font_scale,
    )

    # ── Tổng CF line + Lũy kế line ──────────────────────────────────────────
    total_per_period = (
        df[df["khoan_muc"].isin(km_filter)]
        .groupby("_period")["so_tien_tong"].sum()
        .reindex(periods_sorted, fill_value=0)
    )
    fig.add_trace(
        go.Scatter(
            x=x_numeric, y=total_per_period.values,
            name="Tổng CF (kỳ)",
            mode="lines+markers",
            line=dict(color="#e67e22", width=2.5, dash="dot"),
            marker=dict(size=8, color="#e67e22"),
            customdata=periods_sorted,
            hovertemplate=(
                "<b>Tổng CF kỳ %{customdata}</b><br>"
                "%{y:,.0f} triệu<extra></extra>"
            ),
        ),
        row=1, col=1, secondary_y=False,
    )
    if state.show_cumul:
        cumulative = total_per_period.cumsum()
        fig.add_trace(
            go.Scatter(
                x=x_numeric, y=cumulative.values,
                name="Lũy kế",
                mode="lines+markers",
                line=dict(color="#2c3e50", width=2.5),
                marker=dict(size=8, color="#2c3e50", symbol="diamond"),
                customdata=periods_sorted,
                hovertemplate=(
                    "<b>Lũy kế tới %{customdata}</b><br>"
                    "%{y:,.0f} triệu<extra></extra>"
                ),
            ),
            row=1, col=1, secondary_y=True,
        )

    # ── Layout ──────────────────────────────────────────────────────────────
    height = chart_height_slider(
        "p3_total_height", default=520, min_v=400, max_v=800, step=20,
    )
    base_font = max(8, int(11 * total_font_scale))
    axis_title_font = max(7, int(10 * total_font_scale))
    fig.update_layout(
        barmode="stack",
        legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="left", x=0),
        height=height,
        margin=dict(l=0, r=0, t=80, b=40),
        font=dict(size=base_font),
    )
    fig.update_xaxes(
        tickmode="array", tickvals=x_numeric,
        ticktext=periods_sorted, tickangle=-45,
        tickfont=dict(size=base_font),
    )
    fig.update_yaxes(
        title_text="Dòng tiền (triệu VNĐ)",
        title_font=dict(size=axis_title_font),
        tickfont=dict(size=base_font),
        secondary_y=False,
    )
    if state.show_cumul:
        fig.update_yaxes(
            title_text="Lũy kế (triệu VNĐ)",
            title_font=dict(size=axis_title_font),
            tickfont=dict(size=base_font),
            secondary_y=True,
        )
    st.plotly_chart(fig, use_container_width=True, key="p3_total_chart")
