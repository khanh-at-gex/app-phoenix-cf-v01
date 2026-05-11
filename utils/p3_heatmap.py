"""P3 Tab 2 — Heatmap Net CF (units × periods)."""
from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.charts import HEATMAP_COLORSCALE, fmt_money_short
from utils.ui import chart_font_scale, chart_height_slider


def render(
    *,
    base: pd.DataFrame,
    ordered_labels: list[str],
    label_to_unit: dict[str, str],
) -> None:
    """Render Heatmap tab in-place."""
    st.caption("Xanh = dương · Đỏ = âm · Lọc theo phân loại ổn định và nội/ngoại")

    # ── Filter row ──────────────────────────────────────────────────────────
    fc1, fc2, fc3, fc4, fc5, fc6 = st.columns([3, 2, 2, 2, 2, 3])
    with fc1:
        if "p3_hm_order" not in st.session_state:
            st.session_state.p3_hm_order = []

        def _on_units_change():
            current = st.session_state.p3_hm_units
            prev = st.session_state.p3_hm_order
            new_order = [x for x in prev if x in current]
            for x in current:
                if x not in new_order:
                    new_order.append(x)
            st.session_state.p3_hm_order = new_order

        st.multiselect(
            "Đơn vị", ordered_labels,
            key="p3_hm_units", on_change=_on_units_change,
        )
        sel_labels = st.session_state.p3_hm_order
        sel_units = [label_to_unit[lb] for lb in sel_labels]
    with fc2:
        hm_period = st.segmented_control(
            "Show theo", ["Năm", "Quý"],
            default="Năm", key="p3_hm_period",
        ) or "Năm"
    with fc3:
        on_dinh_val = st.segmented_control(
            "Phân loại ổn định", ["Tất cả", "Ổn định", "Không ổn định"],
            default="Tất cả", key="p3_hm_on_dinh",
        ) or "Tất cả"
    with fc4:
        noi_ngoai_val = st.segmented_control(
            "Phân loại nội/ngoại", ["Tất cả", "Bên trong", "Bên ngoài"],
            default="Tất cả", key="p3_hm_noi_ngoai",
        ) or "Tất cả"
    with fc5:
        km_val = st.segmented_control(
            "Khoản mục", ["Tất cả", "CFO", "CFI", "CFF"],
            default="Tất cả", key="p3_hm_km",
        ) or "Tất cả"

    if km_val != "Tất cả":
        ct_scope = base[base["khoan_muc"] == km_val]
    else:
        ct_scope = base[base["khoan_muc"].isin(["CFO", "CFI", "CFF"])]
    hm_ct_opts = sorted(ct_scope["chi_tieu"].dropna().unique().tolist())

    with fc6:
        sel_chi_tieu = st.multiselect(
            "Loại giao dịch", hm_ct_opts, key="p3_hm_chi_tieu",
        )

    # ── Apply filters ───────────────────────────────────────────────────────
    if hm_period == "Quý":
        hm = base[base["quy"].notna()].copy()
    else:
        hm = base.copy()

    if on_dinh_val != "Tất cả":
        hm = hm[hm["phan_loai_on_dinh_khong_on_dinh"] == on_dinh_val]
    if noi_ngoai_val != "Tất cả":
        hm = hm[hm["phan_loai_ben_trong_ben_ngoai"] == noi_ngoai_val]
    if km_val != "Tất cả":
        hm = hm[hm["khoan_muc"] == km_val]
    else:
        hm = hm[hm["khoan_muc"].isin(["CFO", "CFI", "CFF"])]
    if sel_units:
        hm = hm[hm["ma_don_vi"].isin(sel_units)]
    if sel_chi_tieu:
        hm = hm[hm["chi_tieu"].isin(sel_chi_tieu)]

    if hm.empty:
        st.info("Không có dữ liệu với bộ lọc hiện tại.")
        return

    # ── Pivot ──────────────────────────────────────────────────────────────
    if hm_period == "Quý":
        hm["period"] = hm["nam"].astype(str) + "-Q" + hm["quy"].astype(str)
    else:
        hm["period"] = hm["nam"].astype(str)
    pivot = (
        hm.groupby(["ma_don_vi", "period"])["so_tien_tong"]
        .sum().reset_index()
        .pivot(index="ma_don_vi", columns="period", values="so_tien_tong")
    )
    if hm_period == "Quý":
        sorted_periods = sorted(
            pivot.columns.tolist(),
            key=lambda p: (int(p.split("-")[0]), int(p.split("-Q")[1])),
        )
    else:
        sorted_periods = sorted(pivot.columns.tolist(), key=lambda p: int(p))

    # Row order: theo thứ tự user chọn trong filter; nếu rỗng, theo folder order
    if sel_units:
        row_order = [u for u in sel_units if u in pivot.index]
    else:
        row_order = [
            label_to_unit[lb] for lb in ordered_labels
            if label_to_unit[lb] in pivot.index
        ]
    remaining = [u for u in pivot.index if u not in row_order]
    pivot = pivot.loc[row_order + remaining][sorted_periods]

    units = pivot.index.tolist()
    periods = pivot.columns.tolist()
    z_vals = pivot.values.tolist()
    annot = [[fmt_money_short(v) for v in row] for row in pivot.values]

    flat = [float(v) for row in pivot.values for v in row if pd.notna(v)]
    z_abs = max(abs(min(flat)), abs(max(flat))) if flat else 1_000

    # Nice colorbar ticks (round to nearest order of magnitude)
    mag = 10 ** max(0, math.floor(math.log10(z_abs)) - 1) if z_abs > 0 else 1_000
    step = mag
    while z_abs / step > 6:
        step *= 2
    n_steps = int(z_abs // step)
    tickvals = [i * step for i in range(-n_steps, n_steps + 1)]
    ticktext = [fmt_money_short(v) for v in tickvals]

    cell_h = max(34, min(50, 680 // max(len(units), 1)))
    base_cell_font = max(9, min(12, cell_h - 22))

    hm_font_scale = chart_font_scale("p3_hm_font")
    cell_font_size = max(7, int(base_cell_font * hm_font_scale))
    axis_font_size = max(7, int(11 * hm_font_scale))

    fig = go.Figure(go.Heatmap(
        z=z_vals, x=periods, y=units,
        text=annot, texttemplate="%{text}",
        textfont={"size": cell_font_size, "color": "#1a1a1a"},
        colorscale=HEATMAP_COLORSCALE,
        zmin=-z_abs, zmax=z_abs,
        colorbar=dict(
            tickvals=tickvals, ticktext=ticktext,
            thickness=14, len=0.85,
            tickfont=dict(size=max(7, int(10 * hm_font_scale))),
            title=dict(text="", side="right"),
        ),
        hovertemplate="<b>%{y}</b><br>%{x}<br><b>%{text}</b> (%{z:,.0f} triệu)<extra></extra>",
    ))
    hm_height = chart_height_slider(
        "p3_hm_height",
        default=max(380, len(units) * cell_h + 130),
        min_v=300, max_v=800, step=50,
    )
    fig.update_layout(
        xaxis=dict(
            tickangle=-45, side="bottom",
            tickfont=dict(size=max(7, int(10 * hm_font_scale))),
            fixedrange=True,
        ),
        yaxis=dict(
            autorange="reversed",
            tickfont=dict(size=axis_font_size),
            fixedrange=True,
        ),
        height=hm_height,
        margin=dict(l=0, r=0, t=6, b=80),
        plot_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True, key="p3_heatmap")
