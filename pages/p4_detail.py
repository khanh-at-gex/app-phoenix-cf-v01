import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.charts import GROUP_COLORS, fmt_money
from utils.data_loader import load_data

st.header("Chi tiết CTTV")

with st.spinner("Đang tải dữ liệu..."):
    data = load_data()

df_report = data["report"]
df_kd = data["key_drivers"]
df_rc = data["ratio_commit"]
df_adl = data["adl"]
df_summary = data["summary"]

KHOAN_MUC_COLORS = {"CFO": "#4C72B0", "CFI": "#55A868", "CFF": "#C44E52"}

_SHEET_LABELS = [
    ("report_status",       "Report"),
    ("key_drivers_status",  "Key Drivers"),
    ("ratio_commit_status", "Ratio Commit"),
    ("adl_input_status",    "ADL Input"),
]


def _period_label(df: pd.DataFrame) -> pd.Series:
    """'YYYY-QN' when quy is present, else 'YYYY'."""
    base = df["nam"].astype(str)
    mask = df["quy"].notna()
    if mask.any():
        return base.where(~mask, df["nam"].astype(str) + "-Q" + df["quy"].astype(str))
    return base


def _color_amount(series: pd.Series) -> list[str]:
    """Pandas Styler function: green for positive, red for negative amounts."""
    styles = []
    for v in series:
        if isinstance(v, str) and v.startswith("-"):
            styles.append("color: #e74c3c; font-weight: bold")
        elif v == "—":
            styles.append("")
        else:
            styles.append("color: #27ae60; font-weight: bold")
    return styles


# ── Page-level filters ───────────────────────────────────────────────────────
# Build ordered unit list: folder number order, multi-unit folders show unit suffix
_report_units = set(df_report["ma_don_vi"].dropna().unique())
_unit_folder = (
    df_summary[
        df_summary["ma_don_vi"].isin(_report_units)
        & df_summary["folder_name"].notna()
        & ~df_summary["folder_name"].str.startswith("00")
    ][["folder_name", "ma_don_vi"]]
    .drop_duplicates()
    .sort_values("folder_name")
)
_folder_counts = _unit_folder["folder_name"].value_counts()
_unit_folder = _unit_folder.copy()
_unit_folder["label"] = _unit_folder.apply(
    lambda r: r["folder_name"]
    if _folder_counts[r["folder_name"]] == 1
    else f"{r['folder_name']} — {r['ma_don_vi']}",
    axis=1,
)
_label_to_unit = dict(zip(_unit_folder["label"], _unit_folder["ma_don_vi"]))
_ordered_labels = _unit_folder["label"].tolist()

if not _ordered_labels:
    st.warning("Không có dữ liệu đơn vị.")
    st.stop()

col_a, col_b = st.columns([2, 3])
with col_a:
    selected_label = st.selectbox("ĐƠN VỊ", _ordered_labels, key="p4_unit_label")
    selected_unit = _label_to_unit[selected_label]
with col_b:
    selected_khoan_muc = st.multiselect(
        "KHOẢN MỤC",
        ["CFO", "CFI", "CFF"],
        default=["CFO", "CFI", "CFF"],
        key="p4_khoan_muc",
    )

# ── Global filter values ─────────────────────────────────────────────────────
nam_list = [int(x) for x in st.session_state.get("global_nam", list(range(2026, 2031)))]
quy_list = [int(x) for x in st.session_state.get("global_quy", [1, 2, 3, 4])]

# ── Unit data & header ───────────────────────────────────────────────────────
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

# ── Sheet status bar ─────────────────────────────────────────────────────────
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

# ── Base filter ──────────────────────────────────────────────────────────────
quy_mask = unit_df["quy"].isna() | unit_df["quy"].isin(quy_list)
filtered = unit_df[unit_df["nam"].isin(nam_list) & quy_mask]

# ── Chart: stacked bars CFO/CFI/CFF + Tổng CF + Lũy kế ─────────────────────
st.subheader("Dòng tiền theo thời gian")

chart_base = filtered[filtered["quy"].notna()]

if chart_base.empty:
    st.info("Không có dữ liệu phân kỳ theo quý cho đơn vị này.")
else:
    km_filter = selected_khoan_muc if selected_khoan_muc else ["CFO", "CFI", "CFF"]

    # Bars: selected khoan_muc only
    cf_detail = (
        chart_base[chart_base["khoan_muc"].isin(km_filter)]
        .groupby(["nam", "quy", "khoan_muc"])["so_tien_tong"]
        .sum()
        .reset_index()
        .sort_values(["nam", "quy"])
    )
    cf_detail["period"] = _period_label(cf_detail)

    # Tổng CF and Lũy kế: same km_filter so the line matches the visible bars
    cf_total = (
        chart_base[chart_base["khoan_muc"].isin(km_filter)]
        .groupby(["nam", "quy"])["so_tien_tong"]
        .sum()
        .reset_index()
        .sort_values(["nam", "quy"])
    )
    cf_total["period"] = _period_label(cf_total)

    fig = go.Figure()

    for km in ["CFO", "CFI", "CFF"]:
        if km not in km_filter:
            continue
        km_data = cf_detail[cf_detail["khoan_muc"] == km]
        if not km_data.empty:
            fig.add_trace(go.Bar(
                x=km_data["period"],
                y=km_data["so_tien_tong"],
                name=km,
                marker_color=KHOAN_MUC_COLORS[km],
                marker_opacity=0.85,
            ))

    if not cf_total.empty:
        fig.add_trace(go.Scatter(
            x=cf_total["period"],
            y=cf_total["so_tien_tong"],
            name="Tổng CF",
            mode="lines+markers",
            line=dict(color="#e67e22", width=2.5, dash="dot"),
        ))

    fig.update_layout(
        barmode="group",
        bargroupgap=0.05,
        yaxis=dict(title="Số tiền (đơn vị: triệu VND)"),
        xaxis=dict(
            tickangle=-45,
            rangeslider=dict(visible=True, thickness=0.05),
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=520,
        margin=dict(l=0, r=0, t=40, b=60),
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Section 1: Chi tiết chỉ tiêu ────────────────────────────────────────────
st.subheader("Chi tiết chỉ tiêu — Sheet Report")

sec_col_a, sec_col_b = st.columns(2)
with sec_col_a:
    filter_km = st.multiselect(
        "Khoản mục",
        ["CFO", "CFI", "CFF"],
        default=selected_khoan_muc if selected_khoan_muc else ["CFO", "CFI", "CFF"],
        key="p4_detail_km",
    )
with sec_col_b:
    chi_tieu_opts = sorted(unit_df["chi_tieu"].dropna().unique().tolist())
    filter_ct = st.multiselect("Chỉ tiêu", chi_tieu_opts, key="p4_detail_ct")

km_detail_mask = unit_df["khoan_muc"].isin(filter_km) if filter_km else pd.Series(True, index=unit_df.index)
ct_detail_mask = unit_df["chi_tieu"].isin(filter_ct) if filter_ct else pd.Series(True, index=unit_df.index)

detail_df = unit_df[
    unit_df["nam"].isin(nam_list) & quy_mask & km_detail_mask & ct_detail_mask
].copy()

if detail_df.empty:
    st.info("Không có dữ liệu với bộ lọc hiện tại.")
else:
    want = [
        "khoan_muc", "code", "chi_tieu",
        "nam", "quy", "so_tien_tong",
        "phan_loai_on_dinh_khong_on_dinh", "phan_loai_ben_trong_ben_ngoai",
        "doi_tuong_giao_dich_kinh_te",
    ]
    show = detail_df[[c for c in want if c in detail_df.columns]].copy()
    show["so_tien_tong"] = show["so_tien_tong"].map(fmt_money)
    show = show.rename(columns={
        "khoan_muc": "Khoản mục",
        "code": "Code",
        "chi_tieu": "Chỉ tiêu",
        "nam": "Năm",
        "quy": "Quý",
        "so_tien_tong": "Số tiền (triệu)",
        "phan_loai_on_dinh_khong_on_dinh": "Ổn định",
        "phan_loai_ben_trong_ben_ngoai": "Nội/Ngoại",
        "doi_tuong_giao_dich_kinh_te": "Đối tượng",
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
        "code", "chi_tieu", "cau_phan_value_chain",
        "key_drivers", "phan_loai_on_dinh_khong_on_dinh",
        "rationale_on_dinh_khong_on_dinh",
    ]
    kd_show = kd_df[[c for c in kd_want if c in kd_df.columns]].rename(columns={
        "code": "Code",
        "chi_tieu": "Chỉ tiêu",
        "cau_phan_value_chain": "Value Chain",
        "key_drivers": "Key Drivers",
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
    rc_quy_mask = rc_df["quy"].isna() | rc_df["quy"].isin(quy_list)
    rc_df = rc_df[rc_df["nam"].isin(nam_list) & rc_quy_mask].copy()
    rc_df["period"] = _period_label(rc_df)

    commitments = rc_df["chi_tieu_cam_ket"].dropna().unique().tolist()
    if not commitments:
        st.info("Không có dữ liệu Covenant cho kỳ đã chọn.")
    else:
        tabs = st.tabs([str(c) for c in commitments])
        for tab_i, (tab, commit) in enumerate(zip(tabs, commitments)):
            with tab:
                sub = rc_df[rc_df["chi_tieu_cam_ket"] == commit].sort_values(["nam", "quy"])
                if sub.empty:
                    continue

                threshold_vals = sub["gia_tri_cam_ket"].dropna()
                threshold = float(threshold_vals.iloc[0]) if not threshold_vals.empty else None

                fig = go.Figure()
                sub_status = sub["status"].str.strip().str.lower() if sub["status"].notna().any() else sub["status"]
                for status_val, color in [("ok", "#28a745"), ("break", "#dc3545")]:
                    seg = sub[sub_status == status_val]
                    if not seg.empty:
                        fig.add_trace(go.Scatter(
                            x=seg["period"],
                            y=seg["gia_tri_thuc_hien"],
                            mode="lines+markers",
                            name=f"Thực hiện ({status_val})",
                            line=dict(color=color, width=2),
                        ))

                if threshold is not None:
                    fig.add_hline(
                        y=threshold,
                        line_dash="dash",
                        line_color="orange",
                        annotation_text=f"Cam kết: {threshold:,.2f}",
                    )

                fig.update_layout(
                    height=300,
                    margin=dict(l=0, r=0, t=30, b=0),
                    showlegend=True,
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
            "nam": "Năm",
            "giai_doan_nganh": "Giai đoạn ngành",
            "vi_the_canh_tranh": "Vị thế cạnh tranh",
            "muc_do_tin_cay": "Mức độ tin cậy",
            "thi_phan_uoc_tinh": "Thị phần (%)",
            "co_so_danh_gia": "Cơ sở đánh giá",
        })
    )
    st.dataframe(adl_show, use_container_width=True, hide_index=True)
