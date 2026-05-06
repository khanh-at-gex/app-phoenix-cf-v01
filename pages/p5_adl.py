import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.charts import GROUP_COLORS
from utils.data_loader import load_data

st.header("Ma trận ADL")

with st.spinner("Đang tải dữ liệu..."):
    data = load_data()

df_adl = data["adl"]
df_summary = data["summary"]

# ── ADL axis definitions (order matters: top→bottom, left→right) ─────────────
POSITIONS = ["Dominant", "Strong", "Favourable", "Tenable", "Weak"]
STAGES = ["Embryonic", "Growth", "Mature", "Aging"]

# Strategy text per cell
STRATEGY = {
    ("Dominant",   "Embryonic"): ("Đầu tư mạnh",        "#155724"),
    ("Dominant",   "Growth"):    ("Đầu tư mạnh",        "#155724"),
    ("Dominant",   "Mature"):    ("Bảo vệ vị thế",      "#1a5276"),
    ("Dominant",   "Aging"):     ("Bảo vệ vị thế",      "#1a5276"),
    ("Strong",     "Embryonic"): ("Đầu tư có chọn lọc", "#1e8449"),
    ("Strong",     "Growth"):    ("Đầu tư tăng trưởng", "#155724"),
    ("Strong",     "Mature"):    ("Đầu tư có chọn lọc", "#1e8449"),
    ("Strong",     "Aging"):     ("Giữ / Thu hoạch",    "#7d6608"),
    ("Favourable", "Embryonic"): ("Tăng trưởng chọn lọc","#1e8449"),
    ("Favourable", "Growth"):    ("Tăng trưởng chọn lọc","#1e8449"),
    ("Favourable", "Mature"):    ("Thu hoạch / Tái cơ cấu","#7d6608"),
    ("Favourable", "Aging"):     ("Thu hoạch",           "#7d6608"),
    ("Tenable",    "Embryonic"): ("Đầu tư chọn lọc",    "#7d6608"),
    ("Tenable",    "Growth"):    ("Giữ / Tái cơ cấu",   "#922b21"),
    ("Tenable",    "Mature"):    ("Thu hoạch",           "#922b21"),
    ("Tenable",    "Aging"):     ("Thoái vốn",           "#7b241c"),
    ("Weak",       "Embryonic"): ("Tái cơ cấu / Thoái", "#922b21"),
    ("Weak",       "Growth"):    ("Tái cơ cấu / Thoái", "#922b21"),
    ("Weak",       "Mature"):    ("Thoái vốn",           "#7b241c"),
    ("Weak",       "Aging"):     ("Thoái vốn",           "#7b241c"),
}

def _badge(text: str, color: str) -> str:
    return (
        f'<span style="background:{color};color:white;padding:2px 8px;'
        f'border-radius:10px;font-size:11px;margin:2px;display:inline-block">'
        f"{text}</span>"
    )



# ── Global filters ───────────────────────────────────────────────────────────
nhom = st.session_state.get("global_nhom", "Tất cả")
all_years = sorted(df_adl["nam"].dropna().unique().tolist())

tab1, tab2 = st.tabs(["🗺️ Ma trận", "📋 Bảng tổng hợp"])

# ── TAB 1: ADL Matrix ────────────────────────────────────────────────────────
with tab1:
    col_yr, _ = st.columns([1, 3])
    with col_yr:
        sel_year = st.selectbox(
            "Năm",
            all_years if all_years else [2026],
            index=0,
            key="adl_year",
        )

    adl_yr = df_adl[df_adl["nam"] == sel_year].copy()

    # Apply NHÓM filter via df_summary group lookup
    if nhom != "Tất cả":
        grp_map = df_summary.set_index("ma_don_vi")["group"].to_dict()
        adl_yr = adl_yr[adl_yr["ma_don_vi"].map(grp_map) == nhom]

    # Header row: stage labels
    header_cols = st.columns([1] + [2] * len(STAGES))
    header_cols[0].markdown("**Vị thế**")
    for j, stage in enumerate(STAGES):
        header_cols[j + 1].markdown(f"<div style='text-align:center;font-weight:700'>{stage}</div>", unsafe_allow_html=True)

    st.markdown("<hr style='margin:4px 0'>", unsafe_allow_html=True)

    # Grid rows
    for pos in POSITIONS:
        row_cols = st.columns([1] + [2] * len(STAGES))
        row_cols[0].markdown(f"**{pos}**")

        for j, stage in enumerate(STAGES):
            strat_text, strat_color = STRATEGY.get((pos, stage), ("—", "#888"))

            # Units in this cell
            cell_units = adl_yr[
                (adl_yr["vi_the_canh_tranh"] == pos) &
                (adl_yr["giai_doan_nganh"] == stage)
            ]

            grp_map = df_summary.set_index("ma_don_vi")["group"].to_dict()
            badges = ""
            for _, r in cell_units.iterrows():
                grp = grp_map.get(r["ma_don_vi"], "—")
                color = GROUP_COLORS.get(str(grp), "#6c757d")
                badges += _badge(str(r["ma_don_vi"]), color)

            cell_html = (
                f'<div style="border:1px solid #e2e8f0;border-radius:6px;padding:8px;'
                f'min-height:70px;background:#ffffff;box-shadow:0 1px 2px rgba(0,0,0,0.05)">'
                f'<div style="font-size:10px;color:{strat_color};font-weight:600;margin-bottom:4px">'
                f"{strat_text}</div>"
                f"{badges}"
                f"</div>"
            )
            row_cols[j + 1].markdown(cell_html, unsafe_allow_html=True)

        st.markdown("<div style='margin-bottom:4px'></div>", unsafe_allow_html=True)

    st.caption(f"Hiển thị năm {sel_year}. Chỉ có {len(adl_yr['ma_don_vi'].unique())} đơn vị đã nộp ADL input.")

# ── TAB 2: Summary table ─────────────────────────────────────────────────────
with tab2:
    adl_show = df_adl.copy()

    # Apply NHÓM filter
    grp_map = df_summary.set_index("ma_don_vi")["group"].to_dict()
    adl_show["Group"] = adl_show["ma_don_vi"].map(grp_map)
    if nhom != "Tất cả":
        adl_show = adl_show[adl_show["Group"] == nhom]

    # Apply NĂM filter
    nam_list = st.session_state.get("global_nam", list(range(2026, 2031)))
    adl_show = adl_show[adl_show["nam"].isin([int(x) for x in nam_list])]

    if adl_show.empty:
        st.info("Không có dữ liệu ADL với bộ lọc hiện tại.")
    else:
        want = ["ma_don_vi", "ten_don_vi", "Group", "nam",
                "giai_doan_nganh", "vi_the_canh_tranh",
                "muc_do_tin_cay", "thi_phan_uoc_tinh", "co_so_danh_gia"]
        display = (
            adl_show[[c for c in want if c in adl_show.columns]]
            .sort_values(["ma_don_vi", "nam"])
            .rename(columns={
                "ma_don_vi":         "Mã ĐV",
                "ten_don_vi":        "Tên đơn vị",
                "nam":               "Năm",
                "giai_doan_nganh":   "Giai đoạn ngành",
                "vi_the_canh_tranh": "Vị thế cạnh tranh",
                "muc_do_tin_cay":    "Mức độ tin cậy",
                "thi_phan_uoc_tinh": "Thị phần (%)",
                "co_so_danh_gia":    "Cơ sở đánh giá",
            })
        )
        st.dataframe(display, use_container_width=True, hide_index=True)

