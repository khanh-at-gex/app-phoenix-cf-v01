"""
Shared filter + data prep cho cả 2 Sankey tab (Plotly + ECharts).

Trả về `SankeyData` chứa:
- `sk`: raw filtered DataFrame (cho expander "Xem dữ liệu gốc")
- `agg`: aggregated DataFrame với cột `_src`, `_tgt` (sau VAS swap)
- `sk_loai`: "Thu" / "Chi" / "Tất cả" — caller dùng để adjust UI/caption

Caller (Plotly hoặc ECharts) chỉ cần render từ `agg`. Filter UI + filter logic
+ VAS swap chung 1 chỗ → tránh duplicate ~120 dòng giữa 2 file.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st


@dataclass
class SankeyData:
    sk: pd.DataFrame      # raw filtered, cho expander
    agg: pd.DataFrame     # aggregated với _src, _tgt
    sk_loai: str          # "Thu" / "Chi" / "Tất cả"


def render_sankey_filters_and_prepare(
    *,
    df_report: pd.DataFrame,
    nam_list: list[int],
    quy_list: list[int],
    nhom: str,
    unit_group: dict[str, str],
    ordered_labels: list[str],
    label_to_unit: dict[str, str],
    key_prefix: str,
    default_noi_ngoai: str = "Bên trong",
) -> SankeyData | None:
    """
    Render filter row 1 + row 2 + áp dụng filters + VAS swap.

    Returns None khi data rỗng (caller return early).
    `key_prefix`: prefix session_state key, vd. "p3_sk" hoặc "p3_ec".
    `ordered_labels` / `label_to_unit`: từ build_unit_label_list — dùng để
    hiển thị "Đơn vị" filter giống P4 (folder + ma_don_vi).
    """
    sk_base = df_report[
        df_report["doi_tuong_giao_dich_kinh_te"].notna()
        & df_report["nam"].isin(nam_list)
        & (df_report["quy"].isna() | df_report["quy"].isin(quy_list))
    ].copy()
    sk_base["group"] = sk_base["ma_don_vi"].map(unit_group)
    if nhom != "Tất cả":
        sk_base = sk_base[sk_base["group"] == nhom]

    # ── Filter row 1 ────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5, c6, c7 = st.columns([2, 2, 2, 2, 2, 2, 3])
    with c1:
        sk_nam = st.multiselect(
            "Năm", nam_list, default=nam_list, key=f"{key_prefix}_nam",
        )
    with c2:
        sk_quy = st.multiselect(
            "Quý", [1, 2, 3, 4], default=quy_list,
            format_func=lambda x: f"Q{x}", key=f"{key_prefix}_quy",
        )
    with c3:
        sk_loai = st.segmented_control(
            "Loại dòng", ["Thu", "Chi", "Tất cả"],
            default="Thu", key=f"{key_prefix}_loai",
        ) or "Thu"
    with c4:
        sk_on_dinh = st.segmented_control(
            "Phân loại ổn định", ["Tất cả", "Ổn định", "Không ổn định"],
            default="Tất cả", key=f"{key_prefix}_on_dinh",
        ) or "Tất cả"
    with c5:
        sk_noi_ngoai = st.segmented_control(
            "Phân loại Nội/Ngoại", ["Tất cả", "Bên trong", "Bên ngoài"],
            default=default_noi_ngoai, key=f"{key_prefix}_noi_ngoai",
        ) or default_noi_ngoai
    with c6:
        sk_km = st.segmented_control(
            "Khoản mục", ["Tất cả", "CFO", "CFI", "CFF"],
            default="Tất cả", key=f"{key_prefix}_km",
        ) or "Tất cả"

    # Loại giao dịch options phụ thuộc Khoản mục
    if sk_km != "Tất cả":
        ct_scope = sk_base[sk_base["khoan_muc"] == sk_km]
    else:
        ct_scope = sk_base[sk_base["khoan_muc"].isin(["CFO", "CFI", "CFF"])]
    ct_opts = sorted(ct_scope["chi_tieu"].dropna().unique().tolist())

    with c7:
        sk_chi_tieu = st.multiselect(
            "Loại giao dịch", ct_opts, key=f"{key_prefix}_chi_tieu",
        )

    # ── Apply filters ──────────────────────────────────────────────────────
    sk = (
        sk_base[sk_base["nam"].isin(sk_nam)].copy()
        if sk_nam else sk_base.iloc[0:0].copy()
    )
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
        return None

    # ── VAS swap: hướng arrow theo dấu so_tien_tong ────────────────────────
    # > 0 = Thu (CTTV nhận): src=counterparty, tgt=ma_don_vi
    # < 0 = Chi (CTTV trả):  src=ma_don_vi,    tgt=counterparty
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

    # ── Row 2: company-centric filter ──────────────────────────────────────
    # Đơn vị filter dùng folder-mapped labels (giống P4) — restrict tới
    # units có trong agg hiện tại. Đối tác filter dùng raw doi_tuong vì
    # external counterparties có thể không có trong df_summary.
    units_in_agg = set(agg["ma_don_vi"].dropna().astype(str).unique())
    visible_unit_labels = [
        lb for lb in ordered_labels if label_to_unit.get(lb) in units_in_agg
    ]
    cp_opts = sorted(
        agg["doi_tuong_giao_dich_kinh_te"].dropna().astype(str).unique().tolist()
    )
    sf1, sf2 = st.columns(2)
    with sf1:
        sel_unit_labels = st.multiselect(
            "Đơn vị", visible_unit_labels, key=f"{key_prefix}_unit",
            help="Đơn vị báo cáo — show cả tiền vào và ra của đơn vị đó",
        )
        sel_units = [label_to_unit[lb] for lb in sel_unit_labels]
    with sf2:
        sel_cp = st.multiselect(
            "Đối tác", cp_opts, key=f"{key_prefix}_cp",
            help="Counterparty của giao dịch",
        )
    if sel_units:
        agg = agg[agg["ma_don_vi"].astype(str).isin(sel_units)]
    if sel_cp:
        agg = agg[
            agg["doi_tuong_giao_dich_kinh_te"].astype(str).isin(sel_cp)
        ]

    if agg.empty:
        st.info("Không còn dữ liệu sau khi filter Đơn vị / Đối tác.")
        return None

    return SankeyData(sk=sk, agg=agg, sk_loai=sk_loai)
