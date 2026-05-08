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
    mode = st.segmented_control(
        "Chế độ", ["Đôi (counterparty ↔ CTTV)", "Chuỗi nhiều cấp"],
        default="Đôi (counterparty ↔ CTTV)", key="p3_sk_mode",
    ) or "Đôi (counterparty ↔ CTTV)"

    if mode.startswith("Chuỗi"):
        _render_chain_sankey(df_report, nam_list, quy_list, nhom, unit_group)
        return

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

    # Total flow per node = max(inflow, outflow) — node nguồn cũng có giá trị.
    node_in: dict[str, float] = {}
    node_out: dict[str, float] = {}
    for s_label, t_label, v in zip(sources, targets, val):
        node_in[t_label] = node_in.get(t_label, 0.0) + v
        node_out[s_label] = node_out.get(s_label, 0.0) + v
    node_total = {
        n: max(node_in.get(n, 0.0), node_out.get(n, 0.0)) for n in all_nodes
    }
    node_labels_with_value = [
        f"<b>{n}</b><br>{fmt_money_short(node_total[n])}"
        if node_total.get(n, 0) > 0 else f"<b>{n}</b>"
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
        arrangement="snap",
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

    # Annotation giá trị trên link đã bỏ — xem qua hover.

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


_DIM_CHOICES = {
    "Đối tác": "doi_tuong_giao_dich_kinh_te",
    "Khoản mục": "khoan_muc",
    "Loại giao dịch": "chi_tieu",
    "Đơn vị": "ma_don_vi",
    "Nhóm": "group",
}


def _render_chain_sankey(
    df_report: pd.DataFrame,
    nam_list: list[int],
    quy_list: list[int],
    nhom: str,
    unit_group: dict[str, str],
) -> None:
    """Multi-level Sankey: user picks 2-5 dims, chain consecutive pairs."""
    base = df_report[
        df_report["doi_tuong_giao_dich_kinh_te"].notna()
        & df_report["nam"].isin(nam_list)
        & (df_report["quy"].isna() | df_report["quy"].isin(quy_list))
    ].copy()
    base["group"] = base["ma_don_vi"].map(unit_group)
    if nhom != "Tất cả":
        base = base[base["group"] == nhom]

    # ── Filter row 1 (giống Đôi mode trừ Loại dòng / Đối tác filter) ────────
    c1, c2, c3, c4, c5, c6 = st.columns([2, 2, 2, 2, 2, 2])
    with c1:
        sk_nam = st.multiselect(
            "Năm", nam_list, default=nam_list, key="p3_sk_ch_nam",
        )
    with c2:
        sk_quy = st.multiselect(
            "Quý", [1, 2, 3, 4], default=quy_list,
            format_func=lambda x: f"Q{x}", key="p3_sk_ch_quy",
        )
    with c3:
        sk_loai = st.segmented_control(
            "Loại dòng", ["Thu", "Chi", "Tất cả"],
            default="Thu", key="p3_sk_ch_loai",
        ) or "Thu"
    with c4:
        sk_on_dinh = st.segmented_control(
            "Phân loại ổn định", ["Tất cả", "Ổn định", "Không ổn định"],
            default="Tất cả", key="p3_sk_ch_on_dinh",
        ) or "Tất cả"
    with c5:
        sk_noi_ngoai = st.segmented_control(
            "Phân loại Nội/Ngoại", ["Tất cả", "Bên trong", "Bên ngoài"],
            default="Bên trong", key="p3_sk_ch_noi_ngoai",
        ) or "Bên trong"
    with c6:
        sk_km = st.segmented_control(
            "Khoản mục", ["Tất cả", "CFO", "CFI", "CFF"],
            default="Tất cả", key="p3_sk_ch_km",
        ) or "Tất cả"

    # ── Dim picker ──────────────────────────────────────────────────────────
    dims = st.multiselect(
        "Cấp độ chuỗi (chọn 2-5 theo thứ tự, tạo Sankey N cột)",
        list(_DIM_CHOICES.keys()),
        default=["Đối tác", "Khoản mục", "Đơn vị"],
        key="p3_sk_ch_dims",
        help="Mỗi dim = 1 cột. Hop liên tiếp = 1 link aggregated bằng sum(so_tien_tong).",
    )
    if len(dims) < 2:
        st.info("Chọn tối thiểu 2 cấp độ.")
        return
    if len(dims) > 5:
        st.warning("Tối đa 5 cấp; sẽ dùng 5 cấp đầu.")
        dims = dims[:5]

    # ── Apply filters ───────────────────────────────────────────────────────
    df = base[base["nam"].isin(sk_nam)].copy() if sk_nam else base.iloc[0:0].copy()
    if sk_quy:
        df = df[df["quy"].isin(sk_quy)]
    if sk_on_dinh != "Tất cả":
        df = df[df["phan_loai_on_dinh_khong_on_dinh"] == sk_on_dinh]
    if sk_noi_ngoai != "Tất cả":
        df = df[df["phan_loai_ben_trong_ben_ngoai"] == sk_noi_ngoai]
    if sk_km != "Tất cả":
        df = df[df["khoan_muc"] == sk_km]
    else:
        df = df[df["khoan_muc"].isin(["CFO", "CFI", "CFF"])]
    if sk_loai == "Thu":
        df = df[df["so_tien_tong"] > 0]
    elif sk_loai == "Chi":
        df = df[df["so_tien_tong"] < 0]

    if df.empty:
        st.info("Không có dữ liệu với bộ lọc hiện tại.")
        return

    # ── Build chain agg ─────────────────────────────────────────────────────
    df = df.copy()
    df["_value"] = df["so_tien_tong"].abs()

    hop_aggs = []
    for i in range(len(dims) - 1):
        src_col = _DIM_CHOICES[dims[i]]
        tgt_col = _DIM_CHOICES[dims[i + 1]]
        hop = (
            df.groupby([src_col, tgt_col], dropna=False)["_value"]
            .sum().reset_index()
        )
        hop = hop[hop["_value"] > 0].copy()
        hop = hop.dropna(subset=[src_col, tgt_col])
        hop["_src_id"] = f"L{i}|" + hop[src_col].astype(str)
        hop["_tgt_id"] = f"L{i + 1}|" + hop[tgt_col].astype(str)
        hop_aggs.append(hop[["_src_id", "_tgt_id", "_value"]])

    if not hop_aggs:
        st.info("Không có dữ liệu sau khi build chain.")
        return
    agg = pd.concat(hop_aggs, ignore_index=True)
    if agg.empty:
        st.info("Không có dữ liệu sau khi build chain.")
        return

    # ── Build node list (id → display name) ─────────────────────────────────
    all_node_ids = sorted(set(agg["_src_id"]) | set(agg["_tgt_id"]))
    node_idx = {n: i for i, n in enumerate(all_node_ids)}

    def _strip_level(node_id: str) -> str:
        return node_id.split("|", 1)[1] if "|" in node_id else node_id

    node_names = [_strip_level(n) for n in all_node_ids]

    # Node total = max(in, out)
    node_in: dict[str, float] = {}
    node_out: dict[str, float] = {}
    for s, t, v in zip(agg["_src_id"], agg["_tgt_id"], agg["_value"]):
        node_in[t] = node_in.get(t, 0.0) + v
        node_out[s] = node_out.get(s, 0.0) + v
    node_total = {
        n: max(node_in.get(n, 0.0), node_out.get(n, 0.0)) for n in all_node_ids
    }

    # Apple-style multi-line label
    node_labels = [
        f"<b>{name}</b><br>{fmt_money_short(node_total[nid])}"
        if node_total.get(nid, 0) > 0 else f"<b>{name}</b>"
        for nid, name in zip(all_node_ids, node_names)
    ]

    node_color = []
    for name in node_names:
        g = unit_group.get(name)
        if g == "GEE":
            node_color.append(GEE_COLOR)
        elif g == "GEL":
            node_color.append(GEL_COLOR)
        elif name in ("CFO", "CFI", "CFF"):
            node_color.append("#34495e")
        else:
            node_color.append(_EXTERNAL_COLOR)

    src = [node_idx[s] for s in agg["_src_id"]]
    tgt = [node_idx[t] for t in agg["_tgt_id"]]
    val = agg["_value"].tolist()
    lcolor = [_COLOR_POS] * len(val) if sk_loai == "Thu" else (
        [_COLOR_NEG] * len(val) if sk_loai == "Chi" else
        ["rgba(127,140,141,0.45)"] * len(val)
    )

    sk_font_scale = chart_font_scale("p3_sk_ch_font")
    sk_font = dict(_SANKEY_FONT)
    sk_font["size"] = max(8, int(_SANKEY_FONT["size"] * sk_font_scale))

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            label=node_labels, color=node_color,
            pad=28, thickness=18,
            line=dict(color="rgba(255,255,255,0.6)", width=0.5),
            hovertemplate="%{label}<extra></extra>",
        ),
        link=dict(
            source=src, target=tgt, value=val,
            color=lcolor,
            hovertemplate=(
                "<b>%{source.label} → %{target.label}</b><br>"
                "Giá trị: %{value:,.0f} triệu<extra></extra>"
            ),
        ),
        textfont=sk_font,
    ))

    n_nodes = len(all_node_ids)
    sk_height = chart_height_slider(
        "p3_sk_ch_height",
        default=min(900, max(520, n_nodes * 30 + 140)),
        min_v=400, max_v=1200, step=50,
    )
    fig.update_layout(
        height=sk_height,
        margin=dict(l=90, r=110, t=40, b=40),
        font=sk_font,
        paper_bgcolor="white",
    )
    with st.container(border=True):
        st.plotly_chart(fig, use_container_width=True, key="p3_sankey_chain")

    with st.expander(
        f"🔍 Xem dữ liệu gốc — {len(df):,} rows, {len(agg):,} hop links"
    ):
        st.dataframe(
            agg.sort_values("_value", ascending=False),
            use_container_width=True, hide_index=True,
        )
