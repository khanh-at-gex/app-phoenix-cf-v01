import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.breakdown_chart import (
    BREAKDOWN_OPTIONS,
    add_breakdown_panel,
    compute_label_y_offset,
    compute_periods,
    resolve_breakdown,
)
from utils.charts import GROUP_COLORS, fmt_money
from utils.data_loader import load_data
from utils.filters import (
    apply_global_filters,
    build_unit_label_list,
    get_global_filters,
    period_label,
)
from utils.ui import chart_height_slider

st.header("Chi tiết CTTV")

with st.spinner("Đang tải dữ liệu..."):
    data = load_data()

df_report = data["report"]
df_kd = data["key_drivers"]
df_rc = data["ratio_commit"]
df_adl = data["adl"]
df_summary = data["summary"]

_SHEET_LABELS = [
    ("report_status",       "Report"),
    ("key_drivers_status",  "Key Drivers"),
    ("ratio_commit_status", "Ratio Commit"),
    ("adl_input_status",    "ADL Input"),
]


def _color_amount(series: pd.Series) -> list[str]:
    """Styler: green positive, red negative, blank for em-dash."""
    out = []
    for v in series:
        if isinstance(v, str) and v.startswith("-"):
            out.append("color: #e74c3c; font-weight: bold")
        elif v == "—":
            out.append("")
        else:
            out.append("color: #27ae60; font-weight: bold")
    return out


# ── Page-level filters ───────────────────────────────────────────────────────
ordered_labels, label_to_unit = build_unit_label_list(
    df_summary, units=set(df_report["ma_don_vi"].dropna().unique())
)

if not ordered_labels:
    st.warning("Không có dữ liệu đơn vị.")
    st.stop()

col_a, col_b = st.columns([2, 3])
with col_a:
    selected_label = st.selectbox("ĐƠN VỊ", ordered_labels, key="p4_unit_label")
    selected_unit = label_to_unit[selected_label]
with col_b:
    selected_khoan_muc = st.multiselect(
        "KHOẢN MỤC", ["CFO", "CFI", "CFF"],
        default=["CFO", "CFI", "CFF"],
        key="p4_khoan_muc",
    )

nam_list, quy_list, _ = get_global_filters()

# ── Header ───────────────────────────────────────────────────────────────────
unit_df = df_report[df_report["ma_don_vi"] == selected_unit]
ten_don_vi = unit_df["ten_don_vi"].iloc[0] if not unit_df.empty else selected_unit

unit_sum = df_summary[df_summary["ma_don_vi"] == selected_unit]
group = unit_sum["group"].iloc[0] if not unit_sum.empty else "—"
group_color = GROUP_COLORS.get(str(group), "#6c757d")

st.markdown(
    f"## {ten_don_vi} "
    f'<span style="background:{group_color};color:white;padding:3px 12px;'
    f'border-radius:8px;font-size:14px">{group}</span>',
    unsafe_allow_html=True,
)

# Sheet status bar
if not unit_sum.empty:
    s = unit_sum.iloc[0]
    parts = []
    for col, label in _SHEET_LABELS:
        val = s.get(col)
        if val == "success":
            icon, color = "✓", "#27ae60"
        elif val == "missing_sheet":
            icon, color = "✗", "#e74c3c"
        else:
            icon, color = "—", "#7f8c8d"
        parts.append(
            f'<span style="margin-right:16px;font-size:13px">'
            f'<span style="color:{color};font-weight:700">{icon}</span> {label}</span>'
        )
    st.markdown("".join(parts), unsafe_allow_html=True)

st.divider()

# ── Chart: 3 cột CFO/CFI/CFF mỗi period, optional 2-level stacked ────────────
st.subheader("Dòng tiền theo thời gian")

st.caption("Tùy chọn biểu đồ")
ts_g1, ts_g2 = st.columns([3, 2])
with ts_g1:
    p4_bar_stack = st.segmented_control(
        "Cách phân rã theo", BREAKDOWN_OPTIONS,
        default="Không phân rã", key="p4_bar_stack",
    ) or "Không phân rã"
with ts_g2:
    p4_bar_period = st.segmented_control(
        "Kỳ", ["Năm", "Quý"], default="Quý", key="p4_bar_period",
    ) or "Quý"

filtered = apply_global_filters(unit_df, nam_list, quy_list)
if p4_bar_period == "Quý":
    chart_base = filtered[filtered["quy"].notna()].copy()
else:
    chart_base = filtered.copy()

km_filter = selected_khoan_muc or ["CFO", "CFI", "CFF"]
chart_base = chart_base[chart_base["khoan_muc"].isin(km_filter)]

if chart_base.empty:
    st.info("Không có dữ liệu cho đơn vị này.")
else:
    chart_base, periods_sorted, x_numeric = compute_periods(chart_base, p4_bar_period)
    is_breakdown, stack_col, cat_list, opacity_map = resolve_breakdown(p4_bar_stack, chart_base)
    label_y_offset = compute_label_y_offset(
        chart_base, is_breakdown, stack_col, cat_list, km_filter,
    )

    fig = go.Figure()
    shown_legend: set = set()
    add_breakdown_panel(
        fig, chart_base,
        panel_label=ten_don_vi,
        periods_sorted=periods_sorted, x_numeric=x_numeric,
        is_breakdown=is_breakdown, stack_col=stack_col,
        cat_list=cat_list, opacity_map=opacity_map,
        label_y_offset=label_y_offset,
        km_filter=km_filter, shown_legend=shown_legend,
    )

    # Line "Tổng CF" (sum CFO+CFI+CFF per period) — line + dot
    total_series = (
        chart_base[chart_base["khoan_muc"].isin(km_filter)]
        .groupby("_period")["so_tien_tong"].sum()
        .reindex(periods_sorted, fill_value=0)
    )
    fig.add_trace(go.Scatter(
        x=x_numeric, y=total_series.values,
        name="Tổng CF",
        mode="lines+markers",
        line=dict(color="#e67e22", width=2.5, dash="dot"),
        marker=dict(size=8, color="#e67e22"),
        legendgroup="Tổng CF",
        customdata=periods_sorted,
        hovertemplate=(
            f"<b>Tổng CF — {ten_don_vi}</b><br>%{{customdata}}<br>"
            "%{y:,.0f} triệu<extra></extra>"
        ),
    ))

    ts_height = chart_height_slider("p4_ts_height", default=520, min_v=300, max_v=800)
    fig.update_layout(
        barmode="stack",
        legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="left", x=0),
        height=ts_height,
        margin=dict(l=0, r=0, t=80, b=40),
        font=dict(size=11),
    )
    fig.update_xaxes(
        tickmode="array", tickvals=x_numeric,
        ticktext=periods_sorted, tickangle=-45,
    )
    fig.update_yaxes(title_text="triệu VNĐ", title_font=dict(size=10))
    st.plotly_chart(fig, use_container_width=True, key="p4_timeseries")

st.divider()

# ── Section 1: Chi tiết chỉ tiêu ────────────────────────────────────────────
st.subheader("Chi tiết chỉ tiêu — Sheet Report")

sec_a, sec_b = st.columns(2)
with sec_a:
    filter_km = st.multiselect(
        "Khoản mục", ["CFO", "CFI", "CFF"],
        default=selected_khoan_muc or ["CFO", "CFI", "CFF"],
        key="p4_detail_km",
    )
with sec_b:
    chi_tieu_opts = sorted(unit_df["chi_tieu"].dropna().unique().tolist())
    filter_ct = st.multiselect("Chỉ tiêu", chi_tieu_opts, key="p4_detail_ct")

km_mask = unit_df["khoan_muc"].isin(filter_km) if filter_km else pd.Series(True, index=unit_df.index)
ct_mask = unit_df["chi_tieu"].isin(filter_ct) if filter_ct else pd.Series(True, index=unit_df.index)
quy_mask = unit_df["quy"].isna() | unit_df["quy"].isin(quy_list)
detail_df = unit_df[unit_df["nam"].isin(nam_list) & quy_mask & km_mask & ct_mask].copy()

if detail_df.empty:
    st.info("Không có dữ liệu với bộ lọc hiện tại.")
else:
    want = [
        "khoan_muc", "code", "chi_tieu", "nam", "quy", "so_tien_tong",
        "phan_loai_on_dinh_khong_on_dinh", "phan_loai_ben_trong_ben_ngoai",
        "doi_tuong_giao_dich_kinh_te",
    ]
    show = detail_df[[c for c in want if c in detail_df.columns]].copy()
    show["so_tien_tong"] = show["so_tien_tong"].map(fmt_money)
    show = show.rename(columns={
        "khoan_muc":                       "Khoản mục",
        "code":                            "Code",
        "chi_tieu":                        "Chỉ tiêu",
        "nam":                             "Năm",
        "quy":                             "Quý",
        "so_tien_tong":                    "Số tiền (triệu)",
        "phan_loai_on_dinh_khong_on_dinh": "Ổn định",
        "phan_loai_ben_trong_ben_ngoai":   "Nội/Ngoại",
        "doi_tuong_giao_dich_kinh_te":     "Đối tượng",
    })
    styled = show.style.apply(_color_amount, subset=["Số tiền (triệu)"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

st.divider()

# ── Section 2: Key Drivers ───────────────────────────────────────────────────
st.subheader("Key Drivers — Sheet Key drivers")

kd_df = df_kd[df_kd["ma_don_vi"] == selected_unit]
if kd_df.empty:
    st.info("Không có dữ liệu Key Drivers.")
else:
    kd_want = [
        "code", "chi_tieu", "cau_phan_value_chain", "key_drivers",
        "phan_loai_on_dinh_khong_on_dinh", "rationale_on_dinh_khong_on_dinh",
    ]
    kd_show = kd_df[[c for c in kd_want if c in kd_df.columns]].rename(columns={
        "code":                            "Code",
        "chi_tieu":                        "Chỉ tiêu",
        "cau_phan_value_chain":            "Value Chain",
        "key_drivers":                     "Key Drivers",
        "phan_loai_on_dinh_khong_on_dinh": "Ổn định",
        "rationale_on_dinh_khong_on_dinh": "Rationale",
    })
    st.dataframe(kd_show, use_container_width=True, hide_index=True)

st.divider()

# ── Section 3: Covenant Tracking ────────────────────────────────────────────
st.subheader("Covenant Tracking — Sheet Ratio_commit")

rc_df = df_rc[df_rc["ma_don_vi"] == selected_unit].copy()
if rc_df.empty:
    st.info("Không có dữ liệu Covenant.")
else:
    rc_df = apply_global_filters(rc_df, nam_list, quy_list)
    rc_df["period"] = period_label(rc_df)

    commitments = rc_df["chi_tieu_cam_ket"].dropna().unique().tolist()
    if not commitments:
        st.info("Không có dữ liệu Covenant cho kỳ đã chọn.")
    else:
        cov_height = chart_height_slider(
            "p4_cov_height", default=300, min_v=200, max_v=800,
        )
        tabs = st.tabs([str(c) for c in commitments])
        for tab_i, (tab, commit) in enumerate(zip(tabs, commitments)):
            with tab:
                sub = rc_df[rc_df["chi_tieu_cam_ket"] == commit].sort_values(["nam", "quy"])
                if sub.empty:
                    continue

                threshold_vals = sub["gia_tri_cam_ket"].dropna()
                threshold = float(threshold_vals.iloc[0]) if not threshold_vals.empty else None

                fig = go.Figure()
                sub_status = (
                    sub["status"].str.strip().str.lower()
                    if sub["status"].notna().any() else sub["status"]
                )
                for status_val, color in [("ok", "#28a745"), ("break", "#dc3545")]:
                    seg = sub[sub_status == status_val]
                    if not seg.empty:
                        fig.add_trace(go.Scatter(
                            x=seg["period"], y=seg["gia_tri_thuc_hien"],
                            mode="lines+markers",
                            name=f"Thực hiện ({status_val})",
                            line=dict(color=color, width=2),
                        ))
                if threshold is not None:
                    fig.add_hline(
                        y=threshold, line_dash="dash", line_color="orange",
                        annotation_text=f"Cam kết: {threshold:,.2f}",
                    )
                fig.update_layout(
                    height=cov_height, margin=dict(l=0, r=0, t=30, b=0), showlegend=True,
                )
                st.plotly_chart(fig, use_container_width=True, key=f"p4_covenant_{tab_i}")

                latest = sub.dropna(subset=["gia_tri_thuc_hien"]).tail(1)
                if not latest.empty:
                    r = latest.iloc[0]
                    kc1, kc2, kc3 = st.columns(3)
                    kc1.metric(
                        "Giá trị thực hiện",
                        f"{r['gia_tri_thuc_hien']:,.2f}" if pd.notna(r["gia_tri_thuc_hien"]) else "—",
                    )
                    kc2.metric(
                        "Cam kết",
                        f"{r['gia_tri_cam_ket']:,.2f}" if pd.notna(r["gia_tri_cam_ket"]) else "—",
                    )
                    kc3.metric("Nguồn số liệu", str(r.get("nguon_so_lieu") or "—"))

st.divider()

# ── Section 4: ADL Assessment ────────────────────────────────────────────────
st.subheader("ADL Assessment — Sheet ADL input")

adl_unit = df_adl[df_adl["ma_don_vi"] == selected_unit].copy()
if adl_unit.empty:
    st.info("Không có dữ liệu ADL.")
else:
    adl_want = [
        "nam", "giai_doan_nganh", "vi_the_canh_tranh",
        "muc_do_tin_cay", "thi_phan_uoc_tinh", "co_so_danh_gia",
    ]
    adl_show = (
        adl_unit[[c for c in adl_want if c in adl_unit.columns]]
        .sort_values("nam")
        .rename(columns={
            "nam":               "Năm",
            "giai_doan_nganh":   "Giai đoạn ngành",
            "vi_the_canh_tranh": "Vị thế cạnh tranh",
            "muc_do_tin_cay":    "Mức độ tin cậy",
            "thi_phan_uoc_tinh": "Thị phần (%)",
            "co_so_danh_gia":    "Cơ sở đánh giá",
        })
    )
    st.dataframe(adl_show, use_container_width=True, hide_index=True)
