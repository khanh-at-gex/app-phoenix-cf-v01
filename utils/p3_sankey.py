"""P3 Tab — Sankey dòng tiền nội bộ (Plotly)."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.charts import GEE_COLOR, GEL_COLOR, fmt_money_short
from utils.p3_sankey_common import render_sankey_filters_and_prepare
from utils.ui import chart_font_scale, chart_height_slider

_SANKEY_FONT = dict(
    family="Inter, 'Segoe UI', Roboto, system-ui, sans-serif",
    size=12, color="#2c3e50",
)
_COLOR_POS = "rgba(39,174,96,0.55)"   # Thu — counterparty → đơn vị báo cáo
_COLOR_NEG = "rgba(231,76,60,0.55)"   # Chi — đơn vị báo cáo → counterparty
_EXTERNAL_COLOR = "#7f8c8d"


def render(
    *,
    df_report: pd.DataFrame,
    nam_list: list[int],
    quy_list: list[int],
    nhom: str,
    unit_group: dict[str, str],
    ordered_labels: list[str],
    label_to_unit: dict[str, str],
) -> None:
    """Render Sankey tab in-place."""
    data = render_sankey_filters_and_prepare(
        df_report=df_report, nam_list=nam_list, quy_list=quy_list,
        nhom=nhom, unit_group=unit_group,
        ordered_labels=ordered_labels, label_to_unit=label_to_unit,
        key_prefix="p3_sk",
    )
    if data is None:
        return
    sk = data.sk
    agg = data.agg

    # ── Build Sankey ────────────────────────────────────────────────────────
    sources = agg["_src"].astype(str)
    targets = agg["_tgt"].astype(str)
    all_nodes = sorted(set(sources) | set(targets))
    node_idx = {n: i for i, n in enumerate(all_nodes)}

    node_color = []
    for n in all_nodes:
        g = unit_group.get(n)
        if g == "GEE":
            node_color.append(GEE_COLOR)
        elif g == "GEL":
            node_color.append(GEL_COLOR)
        else:
            node_color.append(_EXTERNAL_COLOR)

    src = sources.map(node_idx).tolist()
    tgt = targets.map(node_idx).tolist()
    val = agg["so_tien_tong"].abs().tolist()
    lcolor = [_COLOR_POS if v > 0 else _COLOR_NEG for v in agg["so_tien_tong"]]
    link_labels = [fmt_money_short(v) for v in val]

    # Append total inflow vào node label
    node_in_total: dict[str, float] = {}
    for n_label, v in zip(targets, val):
        node_in_total[n_label] = node_in_total.get(n_label, 0.0) + v
    node_labels_with_value = [
        f"{n} ({fmt_money_short(node_in_total[n])})" if n in node_in_total else n
        for n in all_nodes
    ]

    # ── Fix node positions (cumulative-value y) để annotations rơi đúng ────
    src_set = set(sources)
    tgt_set = set(targets)
    left_set = src_set - tgt_set
    right_set = tgt_set - src_set
    mid_set = src_set & tgt_set

    node_through: dict[str, float] = {n: 0.0 for n in all_nodes}
    for s, t, v in zip(sources, targets, val):
        node_through[s] += v
        node_through[t] += v

    def _column_y(nodes_in_col: set[str]) -> dict[str, float]:
        if not nodes_in_col:
            return {}
        total = sum(node_through[n] for n in nodes_in_col)
        if total <= 0:
            n = len(nodes_in_col)
            return {k: (i + 0.5) / n for i, k in enumerate(sorted(nodes_in_col))}
        cum, out = 0.0, {}
        for k in sorted(nodes_in_col, key=lambda x: -node_through[x]):
            h = node_through[k] / total
            out[k] = cum + h / 2
            cum += h
        return out

    left_y = _column_y(left_set)
    mid_y = _column_y(mid_set)
    right_y = _column_y(right_set)

    EPS = 0.04
    def _clamp(v: float) -> float:
        return max(EPS, min(1 - EPS, v))

    node_x_list, node_y_list = [], []
    node_x_lookup, node_y_lookup = {}, {}
    for n in all_nodes:
        if n in left_set:
            x_, y_ = EPS, _clamp(left_y[n])
        elif n in right_set:
            x_, y_ = 1 - EPS, _clamp(right_y[n])
        else:
            x_, y_ = 0.5, _clamp(mid_y[n])
        node_x_list.append(x_)
        node_y_list.append(y_)
        node_x_lookup[n] = x_
        node_y_lookup[n] = y_

    n_nodes = len(all_nodes)

    sk_font_scale = chart_font_scale("p3_sk_font")
    sk_font = dict(_SANKEY_FONT)
    sk_font["size"] = max(8, int(_SANKEY_FONT["size"] * sk_font_scale))

    fig = go.Figure(go.Sankey(
        arrangement="fixed",
        node=dict(
            label=node_labels_with_value, color=node_color,
            x=node_x_list, y=node_y_list,
            pad=14, thickness=18,
            line=dict(color="rgba(255,255,255,0.6)", width=0.5),
            hovertemplate="%{label}<extra></extra>",
        ),
        link=dict(
            source=src, target=tgt, value=val,
            label=link_labels,
            color=lcolor, arrowlen=25,
            hovertemplate=(
                "<b>%{source.label} → %{target.label}</b><br>"
                "Giá trị: %{value:,.0f} triệu (%{label})<extra></extra>"
            ),
        ),
        textfont=sk_font,
    ))

    # Annotations giữa link — top 10 lớn nhất, paper yref invert
    SHOW_ALL_LIMIT = 10
    if len(val) <= SHOW_ALL_LIMIT:
        annot_indices = set(range(len(val)))
    else:
        sorted_by_v = sorted(range(len(val)), key=lambda i: -val[i])
        annot_indices = set(sorted_by_v[:SHOW_ALL_LIMIT])

    for i, (s, t, v) in enumerate(zip(sources, targets, val)):
        if i not in annot_indices:
            continue
        mid_x = (node_x_lookup[s] + node_x_lookup[t]) / 2
        mid_y_link = (node_y_lookup[s] + node_y_lookup[t]) / 2
        fig.add_annotation(
            x=mid_x, y=1 - mid_y_link,
            xref="paper", yref="paper",
            text=fmt_money_short(v),
            showarrow=False,
            font=dict(
                family="Arial Black",
                size=max(8, int(10 * sk_font_scale)),
                color="#1a1a1a",
            ),
            bgcolor="rgba(255,255,255,0.95)",
            borderwidth=0,
            borderpad=2,
        )

    sk_height = chart_height_slider(
        "p3_sk_height",
        default=min(800, max(480, n_nodes * 24 + 120)),
        min_v=400, max_v=800, step=50,
    )
    fig.update_layout(
        height=sk_height,
        margin=dict(l=70, r=90, t=40, b=20),
        font=sk_font,
        paper_bgcolor="white",
    )
    with st.container(border=True):
        st.plotly_chart(fig, use_container_width=True, key="p3_sankey")
        st.caption(
            "Mũi tên = hướng tiền chảy thật (theo dấu so_tien_tong, quy ước VAS). "
            "**Xanh = Thu** (đối tác → đơn vị báo cáo) · "
            "**Đỏ = Chi** (đơn vị báo cáo → đối tác) · "
            "Width = |sum(so_tien_tong)| · Đơn vị: triệu VNĐ · "
            "Màu xám = counterparty không thuộc GEE/GEL"
        )

    with st.expander(
        f"🔍 Xem dữ liệu gốc — {len(sk):,} rows raw, {len(agg):,} pairs sau aggregate"
    ):
        tab_raw, tab_agg = st.tabs(["Raw rows", "Aggregated pairs"])
        with tab_raw:
            raw_cols = [
                "ma_don_vi", "ten_don_vi", "code", "khoan_muc", "chi_tieu",
                "nam", "quy", "so_tien_tong",
                "phan_loai_on_dinh_khong_on_dinh",
                "phan_loai_ben_trong_ben_ngoai",
                "doi_tuong_giao_dich_kinh_te",
            ]
            st.dataframe(
                sk[[c for c in raw_cols if c in sk.columns]]
                .sort_values(
                    ["ma_don_vi", "doi_tuong_giao_dich_kinh_te", "nam", "quy"]
                ),
                use_container_width=True, hide_index=True,
            )
        with tab_agg:
            st.dataframe(
                agg.sort_values("so_tien_tong", ascending=False),
                use_container_width=True, hide_index=True,
            )
