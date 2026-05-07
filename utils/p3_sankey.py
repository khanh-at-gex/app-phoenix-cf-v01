"""P3 Tab 1 — Sankey dòng tiền nội bộ."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.charts import GEE_COLOR, GEL_COLOR
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
        sk_nam = st.selectbox("Năm", nam_list, index=0, key="p3_sk_nam")
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
        sk_chi_tieu = st.selectbox(
            "Loại giao dịch", ["Tất cả"] + ct_opts, key="p3_sk_chi_tieu",
        )

    # ── Apply in-tab filters ───────────────────────────────────────────────
    sk = sk_base[sk_base["nam"] == sk_nam].copy()
    if sk_quy:
        sk = sk[sk["quy"].isin(sk_quy)]
    if sk_chi_tieu != "Tất cả":
        sk = sk[sk["chi_tieu"] == sk_chi_tieu]
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

    # ── Build Sankey ────────────────────────────────────────────────────────
    # VAS: so_tien_tong > 0 = thu (CTTV nhận); < 0 = chi (CTTV trả)
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

    n_nodes = len(all_nodes)
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            label=all_nodes, color=node_color,
            pad=14, thickness=18,
            line=dict(color="rgba(255,255,255,0.6)", width=0.5),
            hovertemplate="%{label}<extra></extra>",
        ),
        link=dict(
            source=src, target=tgt, value=val, color=lcolor, arrowlen=25,
            hovertemplate=(
                "<b>%{source.label} → %{target.label}</b><br>"
                "Giá trị: %{value:,.0f} triệu<extra></extra>"
            ),
        ),
        textfont=_SANKEY_FONT,
    ))
    sk_height = chart_height_slider(
        "p3_sk_height",
        default=min(800, max(480, n_nodes * 24 + 120)),
        min_v=400, max_v=800, step=50,
    )
    fig.update_layout(
        height=sk_height,
        margin=dict(l=10, r=10, t=32, b=0),
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
