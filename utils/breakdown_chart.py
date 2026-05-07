"""
Shared logic for the "biểu đồ phân rã dòng tiền" pattern used in P3 Tab 3
and P4 Dòng tiền theo thời gian.

Layout convention per panel:
- 3 cột Khoản mục (CFO/CFI/CFF) cạnh nhau / period (Plotly offsetgroup)
- Optional Level 2 stacked: Ổn định/KOĐ hoặc Bên trong/Bên ngoài
- Outer-end labels (Net per Khoản mục) ở đầu mút bar
- Numeric x với tickvals/ticktext = period labels (workaround Plotly Scatter
  không hỗ trợ offsetgroup trên categorical x; xem ISSUES #9)
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from utils.charts import KHOAN_MUC_COLORS, fmt_money_short

# ── Constants ────────────────────────────────────────────────────────────────

# Offset (theo width category=1) để align label/dot với từng cột Khoản mục
# khi 2-level. Default Plotly bargap=0.2 + 3 offsetgroups → mỗi group rộng
# ~0.267, center cách category center ±0.267.
KM_OFFSET: dict[str, float] = {"CFO": -0.267, "CFI": 0.0, "CFF": 0.267}

STACK_COL: dict[str, str] = {
    "Ổn định/Không ổn định": "phan_loai_on_dinh_khong_on_dinh",
    "Bên trong/Bên ngoài":   "phan_loai_ben_trong_ben_ngoai",
}

CAT_ORDER: dict[str, list[str]] = {
    "Ổn định/Không ổn định": ["Ổn định", "Không ổn định"],
    "Bên trong/Bên ngoài":   ["Bên trong", "Bên ngoài"],
}

BREAKDOWN_OPTIONS: list[str] = [
    "Không phân rã",
    "Bên trong/Bên ngoài",
    "Ổn định/Không ổn định",
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def period_sort_key(p: str) -> tuple[int, int]:
    """Sort key cho period string ('YYYY' hoặc 'YYYY-Qn')."""
    if "-Q" in p:
        return (int(p.split("-Q")[0]), int(p.split("-Q")[1]))
    return (int(p), 0)


def resolve_breakdown(
    breakdown_mode: str,
    chart_base: pd.DataFrame,
) -> tuple[bool, str | None, list[str], dict[str, float]]:
    """
    Returns (is_breakdown, stack_col, cat_list, opacity_map).
    cat_list dùng để giới hạn segments được vẽ; OPACITY_MAP map cat → opacity.
    """
    if breakdown_mode == "Không phân rã":
        return False, None, [], {}
    stack_col = STACK_COL[breakdown_mode]
    cat_list = [
        c for c in CAT_ORDER[breakdown_mode]
        if c in chart_base[stack_col].dropna().unique()
    ]
    opacity_map = (
        {cat_list[0]: 0.95, cat_list[1]: 0.45}
        if len(cat_list) >= 2 else {}
    )
    return True, stack_col, cat_list, opacity_map


def compute_periods(chart_base: pd.DataFrame, period_mode: str) -> tuple[pd.DataFrame, list[str], list[int]]:
    """
    Add `_period` column to chart_base, return (chart_base, periods_sorted, x_numeric).

    period_mode: "Năm" or "Quý". For "Quý", caller should pre-filter rows with
    quy.notna() if needed.
    """
    chart_base = chart_base.copy()
    if period_mode == "Quý":
        chart_base["_period"] = (
            chart_base["nam"].astype(str)
            + "-Q" + chart_base["quy"].astype(int).astype(str)
        )
    else:
        chart_base["_period"] = chart_base["nam"].astype(str)
    periods_sorted = sorted(chart_base["_period"].unique(), key=period_sort_key)
    x_numeric = list(range(len(periods_sorted)))
    return chart_base, periods_sorted, x_numeric


def compute_label_y_offset(
    g_df: pd.DataFrame,
    is_breakdown: bool,
    stack_col: str | None,
    cat_list: list[str],
    km_filter: list[str] | None = None,
    factor: float = 0.06,
) -> float:
    """
    Compute padding để đẩy text label rời khỏi đầu bar — khoảng `factor` của
    y-range của panel. Tối thiểu 1.0 để tránh chia 0.
    """
    nets: list[float] = []
    for km in (km_filter or ["CFO", "CFI", "CFF"]):
        if km not in g_df["khoan_muc"].unique():
            continue
        if is_breakdown:
            s = (
                g_df[(g_df["khoan_muc"] == km) & g_df[stack_col].isin(cat_list)]
                .groupby("_period")["so_tien_tong"].sum()
            )
        else:
            s = g_df[g_df["khoan_muc"] == km].groupby("_period")["so_tien_tong"].sum()
        nets.extend(s.tolist())
    span = (max(nets) - min(nets)) if nets else 1.0
    return max(span, 1.0) * factor


def add_breakdown_panel(
    fig: go.Figure,
    g_df: pd.DataFrame,
    *,
    panel_label: str,
    periods_sorted: list[str],
    x_numeric: list[int],
    is_breakdown: bool,
    stack_col: str | None,
    cat_list: list[str],
    opacity_map: dict[str, float],
    label_y_offset: float,
    km_filter: list[str],
    shown_legend: set[str],
    row: int | None = None,
    col: int | None = None,
) -> None:
    """
    Add bars + outer-end labels for one panel (one ma_don_vi or one chart).
    Mutates `fig` and `shown_legend` in place.

    `row` / `col` chỉ truyền khi fig là `make_subplots` grid. Để None khi
    fig là `go.Figure()` đơn (sẽ raise nếu pass row/col vào figure không phải grid).
    """
    rc_kwargs = {"row": row, "col": col} if row is not None and col is not None else {}

    for km in ["CFO", "CFI", "CFF"]:
        if km not in km_filter or km not in g_df["khoan_muc"].unique():
            continue

        # ── Bars ────────────────────────────────────────────────────────────
        if not is_breakdown:
            series = (
                g_df[g_df["khoan_muc"] == km]
                .groupby("_period")["so_tien_tong"].sum()
                .reindex(periods_sorted, fill_value=0)
            )
            show_leg = km not in shown_legend
            shown_legend.add(km)
            fig.add_trace(
                go.Bar(
                    x=x_numeric, y=series.values,
                    name=km,
                    marker_color=KHOAN_MUC_COLORS[km],
                    opacity=0.9,
                    marker_line=dict(color="rgba(255,255,255,0.5)", width=1),
                    offsetgroup=km,
                    legendgroup=km,
                    showlegend=show_leg,
                    customdata=periods_sorted,
                    hovertemplate=(
                        f"<b>{km}</b><br>%{{customdata}}<br>"
                        f"<b>{panel_label}</b>: %{{y:,.0f}} triệu<extra></extra>"
                    ),
                ),
                **rc_kwargs,
            )
        else:
            for cat in cat_list:
                seg = (
                    g_df[(g_df["khoan_muc"] == km) & (g_df[stack_col] == cat)]
                    .groupby("_period")["so_tien_tong"].sum()
                    .reindex(periods_sorted, fill_value=0)
                )
                trace_name = f"{km} · {cat}"
                show_leg = trace_name not in shown_legend
                shown_legend.add(trace_name)
                fig.add_trace(
                    go.Bar(
                        x=x_numeric, y=seg.values,
                        name=trace_name,
                        marker_color=KHOAN_MUC_COLORS[km],
                        opacity=opacity_map.get(cat, 0.85),
                        marker_line=dict(color="rgba(255,255,255,0.5)", width=1),
                        offsetgroup=km,
                        legendgroup=trace_name,
                        showlegend=show_leg,
                        customdata=periods_sorted,
                        hovertemplate=(
                            f"<b>{km} · {cat}</b><br>%{{customdata}}<br>"
                            f"<b>{panel_label}</b>: %{{y:,.0f}} triệu<extra></extra>"
                        ),
                    ),
                    **rc_kwargs,
                )

        # ── Outer-end Net label (mode='text' only) ─────────────────────────
        if is_breakdown:
            net_series = (
                g_df[(g_df["khoan_muc"] == km) & g_df[stack_col].isin(cat_list)]
                .groupby("_period")["so_tien_tong"].sum()
                .reindex(periods_sorted, fill_value=0)
            )
        else:
            net_series = (
                g_df[g_df["khoan_muc"] == km]
                .groupby("_period")["so_tien_tong"].sum()
                .reindex(periods_sorted, fill_value=0)
            )
        x_label = [i + KM_OFFSET[km] for i in range(len(periods_sorted))]
        y_label = [
            v + label_y_offset if v >= 0 else v - label_y_offset
            for v in net_series.values
        ]
        text_labels = [fmt_money_short(v) for v in net_series.values]
        text_positions = [
            "top center" if v >= 0 else "bottom center"
            for v in net_series.values
        ]
        hover_customdata = [
            [periods_sorted[i], float(net_series.values[i])]
            for i in range(len(periods_sorted))
        ]
        fig.add_trace(
            go.Scatter(
                x=x_label, y=y_label,
                mode="text",
                text=text_labels,
                textposition=text_positions,
                textfont=dict(
                    size=10, color=KHOAN_MUC_COLORS[km], family="Arial Black",
                ),
                showlegend=False,
                customdata=hover_customdata,
                hovertemplate=(
                    f"<b>Net {km}</b><br>%{{customdata[0]}}<br>"
                    f"<b>{panel_label}</b>: %{{customdata[1]:,.0f}} triệu<extra></extra>"
                ),
            ),
            **rc_kwargs,
        )
