"""
Shared filter row + apply logic cho P3 Tab "Biểu đồ phân rã" và "Tổng hợp".

Cả 2 tab đều cùng pattern: 2 hàng controls (Tùy chọn biểu đồ + Bộ lọc dữ liệu)
và cùng filter logic. Helper dưới đây tách phần UI + filter ra 1 chỗ.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import streamlit as st

from utils.breakdown_chart import BREAKDOWN_OPTIONS


@dataclass
class BreakdownFilterState:
    """Trạng thái filter sau khi user thao tác. Caller dùng để apply lên df."""
    breakdown: str = "Không phân rã"
    period_mode: str = "Năm"
    units: list[str] = field(default_factory=list)
    khoan_muc: str = "Tất cả"
    on_dinh: str = "Tất cả"
    noi_ngoai: str = "Tất cả"
    chi_tieu: list[str] = field(default_factory=list)
    yaxis_mode: str | None = None    # chỉ dùng cho multi-panel chart
    show_cumul: bool = False         # chỉ dùng cho aggregate chart


def render_breakdown_filters(
    *,
    prefix: str,
    base: pd.DataFrame,
    ordered_labels: list[str],
    label_to_unit: dict[str, str],
    default_units: list[str] | None = None,
    units_label: str = "Đơn vị",
    with_yaxis: bool = False,
    with_cumul: bool = False,
) -> BreakdownFilterState:
    """
    Render 2-row controls cho breakdown chart. Trả về `BreakdownFilterState`.

    `prefix`: prefix cho session_state key (vd. "p3_bar", "p3_total").
    `default_units`: list `ma_don_vi` mặc định select. None hoặc rỗng = không chọn.
    `with_yaxis`: hiện control "Trục Y Riêng/Chung" (cho multi-panel).
    `with_cumul`: hiện checkbox "Hiển thị Lũy kế" (cho aggregate chart).
    """
    # ── Row 1: Tùy chọn biểu đồ ────────────────────────────────────────────
    st.caption("Tùy chọn biểu đồ")
    if with_yaxis or with_cumul:
        g1, g2, g3 = st.columns([3, 2, 2])
    else:
        g1, g2 = st.columns([3, 2])
        g3 = None

    with g1:
        breakdown = st.segmented_control(
            "Cách phân rã theo", BREAKDOWN_OPTIONS,
            default="Không phân rã", key=f"{prefix}_stack",
        ) or "Không phân rã"
    with g2:
        period_mode = st.segmented_control(
            "Kỳ", ["Năm", "Quý"], default="Năm", key=f"{prefix}_period",
        ) or "Năm"

    yaxis_mode: str | None = None
    show_cumul = False
    if g3 is not None:
        with g3:
            if with_yaxis:
                yaxis_mode = st.segmented_control(
                    "Trục Y", ["Riêng", "Chung"],
                    default="Riêng", key=f"{prefix}_yaxis",
                ) or "Riêng"
            elif with_cumul:
                st.write("")  # spacer for vertical alignment
                show_cumul = st.checkbox(
                    "Hiển thị Lũy kế", value=True, key=f"{prefix}_show_cum",
                    help="Bật/tắt đường lũy kế dòng tiền (secondary Y-axis)",
                )

    # ── Row 2: Bộ lọc dữ liệu ──────────────────────────────────────────────
    st.caption("Bộ lọc dữ liệu")
    f1, f2, f3, f4, f5 = st.columns([3, 2, 2, 2, 3])

    with f1:
        if default_units:
            default_labels = [
                lb for lb in ordered_labels if label_to_unit[lb] in default_units
            ]
        else:
            default_labels = []
        unit_labels = st.multiselect(
            units_label, ordered_labels,
            default=default_labels, key=f"{prefix}_units",
        )
        units = [label_to_unit[lb] for lb in unit_labels]

    with f2:
        khoan_muc = st.segmented_control(
            "Khoản mục", ["Tất cả", "CFO", "CFI", "CFF"],
            default="Tất cả", key=f"{prefix}_km",
        ) or "Tất cả"
    with f3:
        on_dinh = st.segmented_control(
            "Phân loại ổn định", ["Tất cả", "Ổn định", "Không ổn định"],
            default="Tất cả", key=f"{prefix}_on_dinh",
        ) or "Tất cả"
    with f4:
        noi_ngoai = st.segmented_control(
            "Phân loại Nội/Ngoại", ["Tất cả", "Bên trong", "Bên ngoài"],
            default="Tất cả", key=f"{prefix}_noi_ngoai",
        ) or "Tất cả"

    # Loại giao dịch options phụ thuộc Khoản mục
    if khoan_muc != "Tất cả":
        ct_scope = base[base["khoan_muc"] == khoan_muc]
    else:
        ct_scope = base[base["khoan_muc"].isin(["CFO", "CFI", "CFF"])]
    ct_opts = sorted(ct_scope["chi_tieu"].dropna().unique().tolist())

    with f5:
        chi_tieu = st.multiselect(
            "Loại giao dịch", ct_opts, key=f"{prefix}_chi_tieu",
        )

    return BreakdownFilterState(
        breakdown=breakdown,
        period_mode=period_mode,
        units=units,
        khoan_muc=khoan_muc,
        on_dinh=on_dinh,
        noi_ngoai=noi_ngoai,
        chi_tieu=chi_tieu,
        yaxis_mode=yaxis_mode,
        show_cumul=show_cumul,
    )


def apply_breakdown_filters(
    df: pd.DataFrame, state: BreakdownFilterState,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Áp filters (Khoản mục / Ổn định / Nội-Ngoại / Loại giao dịch / Period mode)
    lên df. Trả về (df_filtered, km_filter).

    KHÔNG filter theo `units` — caller tự quyết: P3 Bar dùng units để chia panel,
    P3 Total dùng units để filter (sum across).
    """
    out = df.copy()
    if state.khoan_muc != "Tất cả":
        out = out[out["khoan_muc"] == state.khoan_muc]
        km_filter = [state.khoan_muc]
    else:
        out = out[out["khoan_muc"].isin(["CFO", "CFI", "CFF"])]
        km_filter = ["CFO", "CFI", "CFF"]
    if state.on_dinh != "Tất cả":
        out = out[out["phan_loai_on_dinh_khong_on_dinh"] == state.on_dinh]
    if state.noi_ngoai != "Tất cả":
        out = out[out["phan_loai_ben_trong_ben_ngoai"] == state.noi_ngoai]
    if state.chi_tieu:
        out = out[out["chi_tieu"].isin(state.chi_tieu)]
    if state.period_mode == "Quý":
        out = out[out["quy"].notna()].copy()
    return out, km_filter
