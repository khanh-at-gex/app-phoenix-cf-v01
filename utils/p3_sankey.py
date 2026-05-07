"""P3 Tab 1 — Sankey dòng tiền nội bộ."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.charts import GEE_COLOR, GEL_COLOR, fmt_money_short
from utils.ui import chart_height_slider

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
) -> None:
    """Render Sankey tab in-place."""
    sk_base = df_report[
        df_report["doi_tuong_giao_dich_kinh_te"].notna()
        & df_report["nam"].isin(nam_list)
        & (df_report["quy"].isna() | df_report["quy"].isin(quy_list))
    ].copy()
    sk_base["group"] = sk_base["ma_don_vi"].map(unit_group)
    if nhom != "Tất cả":
        sk_base = sk_base[sk_base["group"] == nhom]

    # ── Filter row ──────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5, c6, c7 = st.columns([2, 2, 2, 2, 2, 2, 3])
    with c1:
        sk_nam = st.multiselect(
            "Năm", nam_list, default=nam_list, key="p3_sk_nam",
        )
    with c2:
        sk_quy = st.multiselect(
            "Quý", [1, 2, 3, 4], default=quy_list,
            format_func=lambda x: f"Q{x}", key="p3_sk_quy",
        )
    with c3:
        sk_loai = st.segmented_control(
            "Loại dòng", ["Thu", "Chi", "Tất cả"],
            default="Thu", key="p3_sk_loai",
        ) or "Thu"
    with c4:
        sk_on_dinh = st.segmented_control(
            "Phân loại ổn định", ["Tất cả", "Ổn định", "Không ổn định"],
            default="Tất cả", key="p3_sk_on_dinh",
        ) or "Tất cả"
    with c5:
        sk_noi_ngoai = st.segmented_control(
            "Phân loại Nội/Ngoại", ["Tất cả", "Bên trong", "Bên ngoài"],
            default="Bên trong", key="p3_sk_noi_ngoai",
        ) or "Bên trong"
    with c6:
        sk_km = st.segmented_control(
            "Khoản mục", ["Tất cả", "CFO", "CFI", "CFF"],
            default="Tất cả", key="p3_sk_km",
        ) or "Tất cả"

    # Loại giao dịch options phụ thuộc Khoản mục
    if sk_km != "Tất cả":
        ct_scope = sk_base[sk_base["khoan_muc"] == sk_km]
    else:
        ct_scope = sk_base[sk_base["khoan_muc"].isin(["CFO", "CFI", "CFF"])]
    ct_opts = sorted(ct_scope["chi_tieu"].dropna().unique().tolist())

    with c7:
        sk_chi_tieu = st.multiselect(
            "Loại giao dịch", ct_opts, key="p3_sk_chi_tieu",
        )

    # ── Apply in-tab filters ───────────────────────────────────────────────
    sk = sk_base[sk_base["nam"].isin(sk_nam)].copy() if sk_nam else sk_base.iloc[0:0].copy()
    if sk_quy:
        sk = sk[sk["quy"].isin(sk_quy)]
    if sk_chi_tieu:
        sk = sk[sk["chi_tieu"].isin(sk_chi_tieu)]
    if sk_on_dinh != "Tất cả":
        sk = sk[sk["phan_loai_on_dinh_khong_on_dinh"] == sk_on_dinh]
    if sk_noi_ngoai != "Tất cả":
        sk = sk[sk["phan_loai_ben_trong_ben_ngoai"] == sk_noi_ngoai]
    if sk_km != "Tất cả":
        sk = sk[sk["khoan_muc"] == sk_km]
    else:
        sk = sk[sk["khoan_muc"].isin(["CFO", "CFI", "CFF"])]

    # ── Aggregate per (source, target) pair ────────────────────────────────
    agg = (
        sk.groupby(["ma_don_vi", "doi_tuong_giao_dich_kinh_te"])["so_tien_tong"]
        .sum()
        .reset_index()
    )
    agg = agg[
        (agg["so_tien_tong"] != 0)
        & (agg["ma_don_vi"] != agg["doi_tuong_giao_dich_kinh_te"])
    ]
    if sk_loai == "Thu":
        agg = agg[agg["so_tien_tong"] > 0]
    elif sk_loai == "Chi":
        agg = agg[agg["so_tien_tong"] < 0]

    if agg.empty:
        st.info("Không có dữ liệu giao dịch nội bộ với bộ lọc hiện tại.")
        return

    # ── VAS swap (so_tien_tong > 0 = Thu) ───────────────────────────────────
    # Mũi tên đi theo HƯỚNG TIỀN CHẢY THẬT, không phải hướng báo cáo.
    agg = agg.copy()
    agg["_src"] = agg.apply(
        lambda r: r["doi_tuong_giao_dich_kinh_te"]
        if r["so_tien_tong"] > 0 else r["ma_don_vi"],
        axis=1,
    )
    agg["_tgt"] = agg.apply(
        lambda r: r["ma_don_vi"]
        if r["so_tien_tong"] > 0 else r["doi_tuong_giao_dich_kinh_te"],
        axis=1,
    )

    # ── Filter row 2: company-centric view ─────────────────────────────────
    # Filter theo raw columns (ma_don_vi = đơn vị báo cáo, doi_tuong = đối tác)
    # → khi pick CADIVI ở "Đơn vị", sẽ thấy CẢ Thu (tiền vào) lẫn Chi (tiền ra)
    # của CADIVI, bất kể chiều arrow sau VAS swap.
    unit_opts = sorted(agg["ma_don_vi"].dropna().astype(str).unique().tolist())
    cp_opts = sorted(
        agg["doi_tuong_giao_dich_kinh_te"].dropna().astype(str).unique().tolist()
    )
    sf1, sf2 = st.columns(2)
    with sf1:
        sel_unit = st.multiselect(
            "Đơn vị (ma_don_vi)", unit_opts, key="p3_sk_unit",
            help="Đơn vị báo cáo — show cả tiền vào và ra của đơn vị đó",
        )
    with sf2:
        sel_cp = st.multiselect(
            "Đối tác (doi_tuong)", cp_opts, key="p3_sk_cp",
            help="Counterparty của giao dịch",
        )
    if sel_unit:
        agg = agg[agg["ma_don_vi"].astype(str).isin(sel_unit)]
    if sel_cp:
        agg = agg[
            agg["doi_tuong_giao_dich_kinh_te"].astype(str).isin(sel_cp)
        ]

    if agg.empty:
        st.info("Không còn dữ liệu sau khi filter Đơn vị / Đối tác.")
        return

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

    # Append total inflow vào node label để node lớn nhìn rõ giá trị
    node_in_total: dict[str, float] = {}
    for n_label, v in zip(targets, val):
        node_in_total[n_label] = node_in_total.get(n_label, 0.0) + v
    node_labels_with_value = [
        f"{n} ({fmt_money_short(node_in_total[n])})" if n in node_in_total else n
        for n in all_nodes
    ]

    # ── FIX node positions để annotations rơi đúng midpoint ────────────────
    # x: source-only nodes (left), target-only (right), both (middle)
    src_set = set(sources)
    tgt_set = set(targets)
    left_set = src_set - tgt_set
    right_set = tgt_set - src_set
    mid_set = src_set & tgt_set

    # Throughput: sum of in/out cho mỗi node để stack y theo size
    node_through: dict[str, float] = {n: 0.0 for n in all_nodes}
    for s, t, v in zip(sources, targets, val):
        node_through[s] += v
        node_through[t] += v

    def _column_y(nodes_in_col: set[str]) -> dict[str, float]:
        """Stack nodes vertically by throughput; return y centers in [0,1]."""
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

    EPS = 0.04  # Plotly requires 0 < x,y < 1; tăng để nodes không sát viền
    def _clamp(v: float) -> float:
        return max(EPS, min(1 - EPS, v))

    node_x_list: list[float] = []
    node_y_list: list[float] = []
    node_y_lookup: dict[str, float] = {}
    node_x_lookup: dict[str, float] = {}
    for n in all_nodes:
        if n in left_set:
            x_, y_ = EPS, _clamp(left_y[n])
        elif n in right_set:
            x_, y_ = 1 - EPS, _clamp(right_y[n])
        else:  # mid
            x_, y_ = 0.5, _clamp(mid_y[n])
        node_x_list.append(x_)
        node_y_list.append(y_)
        node_x_lookup[n] = x_
        node_y_lookup[n] = y_

    n_nodes = len(all_nodes)
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
        textfont=_SANKEY_FONT,
    ))

    # Annotations giữa mỗi link — toạ độ exact = midpoint của 2 node fixed.
    # Plotly Sankey node.y: 0=top, 1=bottom. Paper yref: 0=bottom, 1=top.
    # → invert y khi đặt annotation.
    # Tránh chồng chéo: nếu > 10 link, chỉ show annotation cho top 10 lớn nhất;
    # link nhỏ hơn xem qua hover.
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
            font=dict(family="Arial Black", size=10, color="#1a1a1a"),
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
        font=_SANKEY_FONT,
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
