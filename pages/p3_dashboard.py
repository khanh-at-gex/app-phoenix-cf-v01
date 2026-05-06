import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.data_loader import load_data

st.header("Dashboard chiến lược")

with st.spinner("Đang tải dữ liệu..."):
    data = load_data()

df_report = data["report"]
df_summary = data["summary"]

# Global filters
nam_list = [int(x) for x in st.session_state.get("global_nam", list(range(2026, 2031)))]
quy_list = [int(x) for x in st.session_state.get("global_quy", [1, 2, 3, 4])]
nhom = st.session_state.get("global_nhom", "Tất cả")

# Unit → group mapping from summary
unit_group = (
    df_summary[df_summary["ma_don_vi"].notna() & df_summary["group"].notna()]
    [["ma_don_vi", "group"]]
    .drop_duplicates()
    .set_index("ma_don_vi")["group"]
    .to_dict()
)


def _fmt_annot(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    v = float(v)
    abs_v = abs(v)
    if abs_v >= 1_000_000:
        return f"{v / 1_000_000:.1f}T"
    if abs_v >= 1_000:
        return f"{v / 1_000:.0f}B"
    return f"{v:.0f}"


# ── Tabs (Heatmap first) ──────────────────────────────────────────────────────
tab_heatmap, tab_sankey, tab_cumul = st.tabs([
    "Heatmap Net CF", "Sankey nội bộ CF36", "Tích lũy dư tiền",
])

with tab_sankey:
    st.info("Đang phát triển.")

with tab_cumul:
    st.info("Đang phát triển.")

with tab_heatmap:
    st.caption("Xanh = dương · Đỏ = âm · Lọc theo phân loại ổn định và nội/ngoại")

    # ── Filters ───────────────────────────────────────────────────────────────
    fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 3])
    with fc1:
        on_dinh_val = st.segmented_control(
            "Phân loại ổn định",
            ["Tất cả", "Ổn định", "Không ổn định"],
            default="Tất cả",
            key="p3_hm_on_dinh",
        ) or "Tất cả"
    with fc2:
        noi_ngoai_val = st.segmented_control(
            "Phân loại nội/ngoại",
            ["Tất cả", "Bên trong", "Bên ngoài"],
            default="Tất cả",
            key="p3_hm_noi_ngoai",
        ) or "Tất cả"
    with fc3:
        km_val = st.segmented_control(
            "Khoản mục",
            ["Tất cả", "CFO", "CFI", "CFF"],
            default="Tất cả",
            key="p3_hm_km",
        ) or "Tất cả"

    # Apply global filters — must come before unit list is built
    quy_mask = df_report["quy"].isna() | df_report["quy"].isin(quy_list)
    base = df_report[df_report["nam"].isin(nam_list) & quy_mask].copy()
    base["group"] = base["ma_don_vi"].map(unit_group)
    if nhom != "Tất cả":
        base = base[base["group"] == nhom]

    # Build folder-ordered unit labels (same logic as P4)
    _base_units = set(base["ma_don_vi"].dropna().unique())
    _uf = (
        df_summary[
            df_summary["ma_don_vi"].isin(_base_units)
            & df_summary["folder_name"].notna()
            & ~df_summary["folder_name"].str.startswith("00")
        ][["folder_name", "ma_don_vi"]]
        .drop_duplicates()
        .sort_values("folder_name")
        .copy()
    )
    _fc = _uf["folder_name"].value_counts()
    _uf["label"] = _uf.apply(
        lambda r: r["folder_name"]
        if _fc[r["folder_name"]] == 1
        else f"{r['folder_name']} — {r['ma_don_vi']}",
        axis=1,
    )
    _label_to_unit = dict(zip(_uf["label"], _uf["ma_don_vi"]))
    _ordered_labels = _uf["label"].tolist()

    with fc4:
        sel_labels = st.multiselect("Đơn vị", _ordered_labels, key="p3_hm_units")
        sel_units = [_label_to_unit[lb] for lb in sel_labels]

    # ── Apply in-tab filters ──────────────────────────────────────────────────
    hm = base[base["quy"].notna()].copy()
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

    if hm.empty:
        st.info("Không có dữ liệu với bộ lọc hiện tại.")
    else:
        hm["period"] = hm["nam"].astype(str) + "-Q" + hm["quy"].astype(str)

        pivot = (
            hm.groupby(["ma_don_vi", "period"])["so_tien_tong"]
            .sum()
            .reset_index()
            .pivot(index="ma_don_vi", columns="period", values="so_tien_tong")
        )

        sorted_periods = sorted(
            pivot.columns.tolist(),
            key=lambda p: (int(p.split("-")[0]), int(p.split("-Q")[1])),
        )

        # Folder-ordered rows
        _folder_ordered = [_label_to_unit[lb] for lb in _ordered_labels if _label_to_unit[lb] in pivot.index]
        _remaining = [u for u in pivot.index if u not in _folder_ordered]
        pivot = pivot.loc[_folder_ordered + _remaining][sorted_periods]

        units = pivot.index.tolist()
        periods = pivot.columns.tolist()
        z_vals = pivot.values.tolist()
        annot = [[_fmt_annot(v) for v in row] for row in pivot.values]

        flat = [float(v) for row in pivot.values for v in row if pd.notna(v)]
        z_abs = max(abs(min(flat)), abs(max(flat))) if flat else 1_000

        # Nice colorbar ticks in B/T
        mag = 10 ** max(0, math.floor(math.log10(z_abs)) - 1) if z_abs > 0 else 1_000
        step = mag
        while z_abs / step > 6:
            step *= 2
        n_steps = int(z_abs // step)
        tickvals = [i * step for i in range(-n_steps, n_steps + 1)]
        ticktext = [_fmt_annot(v) for v in tickvals]

        colorscale = [
            [0.00, "#8b0000"],
            [0.35, "#e74c3c"],
            [0.50, "#f5f0eb"],
            [0.65, "#27ae60"],
            [1.00, "#1a5c30"],
        ]

        cell_h = max(34, min(50, 680 // max(len(units), 1)))
        font_size = max(9, min(12, cell_h - 22))

        fig = go.Figure(go.Heatmap(
            z=z_vals,
            x=periods,
            y=units,
            text=annot,
            texttemplate="%{text}",
            textfont={"size": font_size, "color": "#1a1a1a"},
            colorscale=colorscale,
            zmin=-z_abs,
            zmax=z_abs,
            colorbar=dict(
                tickvals=tickvals,
                ticktext=ticktext,
                thickness=14,
                len=0.85,
                title=dict(text="", side="right"),
            ),
            hovertemplate="<b>%{y}</b><br>%{x}<br><b>%{text}</b> (%{z:,.0f} triệu)<extra></extra>",
        ))

        fig.update_layout(
            xaxis=dict(
                tickangle=-45,
                side="bottom",
                tickfont=dict(size=10),
                fixedrange=True,
            ),
            yaxis=dict(
                autorange="reversed",
                tickfont=dict(size=11),
                fixedrange=True,
            ),
            height=max(380, len(units) * cell_h + 130),
            margin=dict(l=0, r=0, t=6, b=80),
            plot_bgcolor="white",
        )
        st.plotly_chart(fig, use_container_width=True, key="p3_heatmap")
