import math

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from utils.charts import (
    GEE_COLOR,
    GEL_COLOR,
    HEATMAP_COLORSCALE,
    KHOAN_MUC_COLORS,
    fmt_money_short,
)
from utils.data_loader import load_data
from utils.filters import (
    apply_global_filters,
    build_unit_label_list,
    get_global_filters,
    unit_group_map,
)

st.header("Dashboard chiến lược")

with st.spinner("Đang tải dữ liệu..."):
    data = load_data()

df_report = data["report"]
df_summary = data["summary"]

nam_list, quy_list, nhom = get_global_filters()
unit_group = unit_group_map(df_summary)

# ── Page-level base DataFrame + folder-ordered unit list ─────────────────────
base = apply_global_filters(df_report, nam_list, quy_list)
base["group"] = base["ma_don_vi"].map(unit_group)
if nhom != "Tất cả":
    base = base[base["group"] == nhom]

_ordered_labels, _label_to_unit = build_unit_label_list(
    df_summary, units=set(base["ma_don_vi"].dropna().unique())
)

# ── Tabs (order matches requirements.md §3 P3) ───────────────────────────────
tab_sankey, tab_heatmap, tab_bar, tab_cumul = st.tabs([
    "Sankey nội bộ CF36", "Heatmap Net CF", "Biểu đồ cột", "Tích lũy dư tiền",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Sankey nội bộ CF36
# ─────────────────────────────────────────────────────────────────────────────
with tab_sankey:
    sk_base = df_report[
        df_report["code"].str.startswith("CF36", na=False)
        & df_report["khoan_muc"].isin(["CFO", "CFI", "CFF"])
        & df_report["nam"].isin(nam_list)
        & (df_report["quy"].isna() | df_report["quy"].isin(quy_list))
    ].copy()
    sk_base["group"] = sk_base["ma_don_vi"].map(unit_group)
    if nhom != "Tất cả":
        sk_base = sk_base[sk_base["group"] == nhom]
    ct_opts = sorted(sk_base["chi_tieu"].dropna().unique().tolist())

    c1, c2, c3, c4, c5, c6 = st.columns([2, 2, 2, 2, 2, 3])
    with c1:
        sk_nam = st.selectbox("Năm", nam_list, index=0, key="p3_sk_nam")
    with c2:
        sk_quy = st.multiselect(
            "Quý", [1, 2, 3, 4], default=quy_list,
            format_func=lambda x: f"Q{x}", key="p3_sk_quy",
        )
    with c3:
        sk_km = st.segmented_control(
            "Khoản mục", ["Tất cả", "CFO", "CFI", "CFF"],
            default="Tất cả", key="p3_sk_km",
        ) or "Tất cả"
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
        sk_chi_tieu = st.selectbox(
            "Loại giao dịch", ["Tất cả"] + ct_opts, key="p3_sk_chi_tieu",
        )

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

    agg = sk.groupby(["ma_don_vi", "ten_don_vi"])["so_tien_tong"].sum().reset_index()
    agg["group"] = agg["ma_don_vi"].map(unit_group)
    agg = agg[agg["group"].isin(["GEE", "GEL"]) & (agg["so_tien_tong"] != 0)]

    if agg.empty:
        st.info("Không có dữ liệu CF36 nội bộ với bộ lọc hiện tại.")
    else:
        COLOR_POS = "rgba(39,174,96,0.55)"
        COLOR_NEG = "rgba(231,76,60,0.55)"

        cttv = agg.sort_values("ten_don_vi").reset_index(drop=True)
        n = len(cttv)
        n_gee = int((cttv["group"] == "GEE").sum())
        n_gel = int((cttv["group"] == "GEL").sum())
        n_tot = max(n, 1)

        node_labels = ["GEE", "GEL", "Tập đoàn (GELEX)"] + cttv["ten_don_vi"].tolist()
        node_x = [0.5, 0.5, 0.99] + [0.01] * n
        node_y = (
            [(n_gee / n_tot) * 0.5, (n_gee / n_tot) + (n_gel / n_tot) * 0.5, 0.5]
            + [0.05 + 0.9 * i / max(n - 1, 1) for i in range(n)]
        )
        node_color = (
            [GEE_COLOR, GEL_COLOR, "#2c3e50"]
            + [GEE_COLOR if g == "GEE" else GEL_COLOR for g in cttv["group"]]
        )

        src, tgt, val, lcolor = [], [], [], []
        for i, row in cttv.iterrows():
            if row["group"] not in ("GEE", "GEL"):
                continue
            net = row["so_tien_tong"]
            mid = 0 if row["group"] == "GEE" else 1
            src.append(3 + i)
            tgt.append(mid)
            val.append(abs(net))
            lcolor.append(COLOR_POS if net >= 0 else COLOR_NEG)
        for grp_name, grp_idx in [("GEE", 0), ("GEL", 1)]:
            grp_net = cttv.loc[cttv["group"] == grp_name, "so_tien_tong"].sum()
            if grp_net == 0:
                continue
            src.append(grp_idx)
            tgt.append(2)
            val.append(abs(grp_net))
            lcolor.append(COLOR_POS if grp_net >= 0 else COLOR_NEG)

        fig = go.Figure(go.Sankey(
            arrangement="snap",
            node=dict(
                label=node_labels, x=node_x, y=node_y, color=node_color,
                pad=12, thickness=18,
                line=dict(color="white", width=0.5),
                hovertemplate="%{label}<extra></extra>",
            ),
            link=dict(
                source=src, target=tgt, value=val, color=lcolor, arrowlen=25,
                hovertemplate=(
                    "<b>%{source.label} → %{target.label}</b><br>"
                    "Giá trị: %{value:,.0f} triệu<extra></extra>"
                ),
            ),
        ))
        fig.update_layout(
            height=max(420, n * 28 + 120),
            margin=dict(l=0, r=0, t=32, b=0),
            font=dict(size=11),
            paper_bgcolor="white",
        )
        st.plotly_chart(fig, use_container_width=True, key="p3_sankey")
        st.caption(
            "Xanh = CTTV nộp lên tập đoàn (net dương) · "
            "Đỏ = CTTV nhận từ tập đoàn (net âm) · Đơn vị: triệu VNĐ"
        )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — Heatmap Net CF
# ─────────────────────────────────────────────────────────────────────────────
with tab_heatmap:
    st.caption("Xanh = dương · Đỏ = âm · Lọc theo phân loại ổn định và nội/ngoại")

    fc1, fc2, fc3, fc4, fc5 = st.columns([2, 2, 2, 3, 3])
    with fc1:
        on_dinh_val = st.segmented_control(
            "Phân loại ổn định", ["Tất cả", "Ổn định", "Không ổn định"],
            default="Tất cả", key="p3_hm_on_dinh",
        ) or "Tất cả"
    with fc2:
        noi_ngoai_val = st.segmented_control(
            "Phân loại nội/ngoại", ["Tất cả", "Bên trong", "Bên ngoài"],
            default="Tất cả", key="p3_hm_noi_ngoai",
        ) or "Tất cả"
    with fc3:
        km_val = st.segmented_control(
            "Khoản mục", ["Tất cả", "CFO", "CFI", "CFF"],
            default="Tất cả", key="p3_hm_km",
        ) or "Tất cả"

    hm_ct_opts = sorted(base["chi_tieu"].dropna().unique().tolist())
    with fc4:
        sel_labels = st.multiselect("Đơn vị", _ordered_labels, key="p3_hm_units")
        sel_units = [_label_to_unit[lb] for lb in sel_labels]
    with fc5:
        sel_chi_tieu = st.multiselect("Chỉ tiêu", hm_ct_opts, key="p3_hm_chi_tieu")

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
    if sel_chi_tieu:
        hm = hm[hm["chi_tieu"].isin(sel_chi_tieu)]

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
        folder_ordered = [
            _label_to_unit[lb] for lb in _ordered_labels
            if _label_to_unit[lb] in pivot.index
        ]
        remaining = [u for u in pivot.index if u not in folder_ordered]
        pivot = pivot.loc[folder_ordered + remaining][sorted_periods]

        units = pivot.index.tolist()
        periods = pivot.columns.tolist()
        z_vals = pivot.values.tolist()
        annot = [[fmt_money_short(v) for v in row] for row in pivot.values]

        flat = [float(v) for row in pivot.values for v in row if pd.notna(v)]
        z_abs = max(abs(min(flat)), abs(max(flat))) if flat else 1_000

        # Nice colorbar ticks
        mag = 10 ** max(0, math.floor(math.log10(z_abs)) - 1) if z_abs > 0 else 1_000
        step = mag
        while z_abs / step > 6:
            step *= 2
        n_steps = int(z_abs // step)
        tickvals = [i * step for i in range(-n_steps, n_steps + 1)]
        ticktext = [fmt_money_short(v) for v in tickvals]

        cell_h = max(34, min(50, 680 // max(len(units), 1)))
        font_size = max(9, min(12, cell_h - 22))

        fig = go.Figure(go.Heatmap(
            z=z_vals, x=periods, y=units,
            text=annot, texttemplate="%{text}",
            textfont={"size": font_size, "color": "#1a1a1a"},
            colorscale=HEATMAP_COLORSCALE,
            zmin=-z_abs, zmax=z_abs,
            colorbar=dict(
                tickvals=tickvals, ticktext=ticktext,
                thickness=14, len=0.85,
                title=dict(text="", side="right"),
            ),
            hovertemplate="<b>%{y}</b><br>%{x}<br><b>%{text}</b> (%{z:,.0f} triệu)<extra></extra>",
        ))
        fig.update_layout(
            xaxis=dict(tickangle=-45, side="bottom", tickfont=dict(size=10), fixedrange=True),
            yaxis=dict(autorange="reversed", tickfont=dict(size=11), fixedrange=True),
            height=max(380, len(units) * cell_h + 130),
            margin=dict(l=0, r=0, t=6, b=80),
            plot_bgcolor="white",
        )
        st.plotly_chart(fig, use_container_width=True, key="p3_heatmap")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — Biểu đồ cột (3-panel grouped bar by GEX/GEE/GEL)
# ─────────────────────────────────────────────────────────────────────────────
with tab_bar:
    st.caption("Tùy chọn biểu đồ")
    g1, g2, g3 = st.columns([2, 3, 2])
    with g1:
        bar_mode = st.segmented_control(
            "Loại biểu đồ", ["Xếp chồng", "Theo nhóm"],
            default="Xếp chồng", key="p3_bar_mode",
        ) or "Xếp chồng"
    with g2:
        bar_stack = st.segmented_control(
            "Cách phân rã theo", ["Ổn định/KOĐ", "Khoản mục", "Bên trong/Bên ngoài"],
            default="Ổn định/KOĐ", key="p3_bar_stack",
        ) or "Ổn định/KOĐ"
    with g3:
        bar_period = st.segmented_control(
            "Kỳ", ["Năm", "Quý"], default="Năm", key="p3_bar_period",
        ) or "Năm"

    st.caption("Bộ lọc dữ liệu")
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        bar_nhom = st.segmented_control(
            "Nhóm", ["Tất cả", "GEE", "GEL"],
            default=nhom if nhom in ["GEE", "GEL"] else "Tất cả",
            key="p3_bar_nhom",
        ) or "Tất cả"
    with f2:
        bar_km = st.segmented_control(
            "Khoản mục", ["Tất cả", "CFO", "CFI", "CFF"],
            default="Tất cả", key="p3_bar_km",
        ) or "Tất cả"
    with f3:
        bar_on_dinh = st.segmented_control(
            "Phân loại ổn định", ["Tất cả", "Ổn định", "Không ổn định"],
            default="Tất cả", key="p3_bar_on_dinh",
        ) or "Tất cả"
    with f4:
        bar_noi_ngoai = st.segmented_control(
            "Phân loại Nội/Ngoại", ["Tất cả", "Bên trong", "Bên ngoài"],
            default="Tất cả", key="p3_bar_noi_ngoai",
        ) or "Tất cả"

    bar = base.copy()
    bar["group"] = bar["ma_don_vi"].map(unit_group)
    if bar_km != "Tất cả":
        bar = bar[bar["khoan_muc"] == bar_km]
    else:
        bar = bar[bar["khoan_muc"].isin(["CFO", "CFI", "CFF"])]
    if bar_on_dinh != "Tất cả":
        bar = bar[bar["phan_loai_on_dinh_khong_on_dinh"] == bar_on_dinh]
    if bar_noi_ngoai != "Tất cả":
        bar = bar[bar["phan_loai_ben_trong_ben_ngoai"] == bar_noi_ngoai]
    if bar_period == "Quý":
        bar = bar[bar["quy"].notna()].copy()
        bar["_period"] = bar["nam"].astype(str) + "-Q" + bar["quy"].astype(int).astype(str)
    else:
        bar["_period"] = bar["nam"].astype(str)

    if bar_nhom == "Tất cả":
        group_defs = [("GEX", None), ("GEE", "GEE"), ("GEL", "GEL")]
    elif bar_nhom == "GEE":
        group_defs = [("GEX", None), ("GEE", "GEE")]
    else:
        group_defs = [("GEX", None), ("GEL", "GEL")]

    if bar.empty:
        st.info("Không có dữ liệu với bộ lọc hiện tại.")
    else:
        CAT_ORDER = {
            "Ổn định/KOĐ":         ["Ổn định", "Không ổn định"],
            "Khoản mục":            ["CFO", "CFI", "CFF"],
            "Bên trong/Bên ngoài":  ["Bên trong", "Bên ngoài"],
        }
        CAT_COLORS = {
            "Ổn định/KOĐ":         {"Ổn định": "#2e7d32", "Không ổn định": "#f57c00"},
            "Khoản mục":            KHOAN_MUC_COLORS,
            "Bên trong/Bên ngoài":  {"Bên trong": "#1565c0", "Bên ngoài": "#6a1b9a"},
        }
        STACK_COL = {
            "Ổn định/KOĐ":         "phan_loai_on_dinh_khong_on_dinh",
            "Khoản mục":            "khoan_muc",
            "Bên trong/Bên ngoài":  "phan_loai_ben_trong_ben_ngoai",
        }

        periods_sorted = sorted(
            bar["_period"].unique(),
            key=lambda p: (int(p.split("-Q")[0]), int(p.split("-Q")[1]))
            if "-Q" in p else (int(p), 0),
        )
        stack_col = STACK_COL[bar_stack]
        cat_list = [c for c in CAT_ORDER[bar_stack] if c in bar[stack_col].dropna().unique()]
        color_map = CAT_COLORS[bar_stack]

        n_cols = len(group_defs)
        fig = make_subplots(
            rows=1, cols=n_cols,
            shared_yaxes=True,
            subplot_titles=[g for g, _ in group_defs],
            horizontal_spacing=0.04,
        )

        shown_legend: set = set()
        for col_idx, (g_label, g_filter) in enumerate(group_defs, start=1):
            g_df = bar if g_filter is None else bar[bar["group"] == g_filter]
            for cat in cat_list:
                cat_series = (
                    g_df[g_df[stack_col] == cat]
                    .groupby("_period")["so_tien_tong"]
                    .sum()
                    .reindex(periods_sorted, fill_value=0)
                )
                show_leg = cat not in shown_legend
                if show_leg:
                    shown_legend.add(cat)
                fig.add_trace(
                    go.Bar(
                        x=periods_sorted, y=cat_series.values,
                        name=str(cat),
                        marker_color=color_map.get(cat),
                        opacity=0.82,
                        marker_line=dict(color="rgba(255,255,255,0.5)", width=1),
                        legendgroup=str(cat),
                        showlegend=show_leg,
                        hovertemplate=(
                            f"<b>{cat}</b><br>%{{x}}<br>"
                            f"<b>{g_label}</b>: %{{y:,.0f}} triệu<extra></extra>"
                        ),
                    ),
                    row=1, col=col_idx,
                )
            total_series = (
                g_df.groupby("_period")["so_tien_tong"]
                .sum()
                .reindex(periods_sorted, fill_value=0)
            )
            fig.add_trace(
                go.Scatter(
                    x=periods_sorted, y=total_series.values,
                    name="Tổng", mode="lines+markers",
                    line=dict(color="#e67e22", width=2, dash="dot"),
                    marker=dict(size=6),
                    legendgroup="Tổng",
                    showlegend=(col_idx == 1),
                    hovertemplate=(
                        f"<b>Tổng {g_label}</b><br>%{{x}}<br>%{{y:,.0f}} triệu<extra></extra>"
                    ),
                ),
                row=1, col=col_idx,
            )

        fig.update_layout(
            barmode="stack" if bar_mode == "Xếp chồng" else "group",
            legend=dict(orientation="h", yanchor="bottom", y=1.08, xanchor="left", x=0),
            height=500,
            margin=dict(l=0, r=0, t=70, b=60),
            font=dict(size=11),
        )
        fig.update_xaxes(
            type="category", categoryorder="array",
            categoryarray=periods_sorted, tickangle=-45,
        )
        fig.update_yaxes(title_text="triệu VNĐ", col=1)
        st.plotly_chart(fig, use_container_width=True, key="p3_bar_chart")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — Tích lũy dư tiền (placeholder)
# ─────────────────────────────────────────────────────────────────────────────
with tab_cumul:
    st.info("Đang phát triển.")
