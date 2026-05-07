import pandas as pd
import streamlit as st

from utils.charts import (
    GROUP_COLORS,
    STATUS_NONE_BADGE,
    STATUS_OK_BADGE,
    STATUS_WARN_BADGE,
)
from utils.data_loader import load_data
from utils.ui import badge

_STATUS_COLORS = {
    "Hoàn chỉnh": STATUS_OK_BADGE,
    "Chưa đủ":   STATUS_WARN_BADGE,
    "Chưa nộp":  STATUS_NONE_BADGE,
}
_SHEET_COLS = ["report_status", "key_drivers_status", "ratio_commit_status", "adl_input_status"]


def _compute_status(row) -> str:
    if pd.isna(row.get("file_path")):
        return "Chưa nộp"
    if all(row.get(s) == "success" for s in _SHEET_COLS):
        return "Hoàn chỉnh"
    return "Chưa đủ"


def _sheet_icon(status) -> str:
    if status == "success":
        return "✓"
    if status == "missing_sheet":
        return "✗"
    return "—"


def _color_status(val: str) -> str:
    if val == "✓":
        return "color: #27ae60; font-weight: bold"
    if val == "✗":
        return "color: #e74c3c; font-weight: bold"
    return "color: #7f8c8d"


st.header("Theo dõi dữ liệu")

with st.spinner("Đang tải dữ liệu..."):
    data = load_data()

df = data["summary"].copy()
df = df[~df["folder_name"].str.startswith("00")]

nhom = st.session_state.get("global_nhom", "Tất cả")
if nhom != "Tất cả":
    df = df[df["group"] == nhom]

df["trang_thai"] = df.apply(_compute_status, axis=1)

# ── KPI row ──────────────────────────────────────────────────────────────────
n_total = len(df)
n_hc = int((df["trang_thai"] == "Hoàn chỉnh").sum())
n_cd = int((df["trang_thai"] == "Chưa đủ").sum())
n_cn = int((df["trang_thai"] == "Chưa nộp").sum())

c1, c2, c3 = st.columns(3)
c1.metric("HOÀN CHỈNH", f"{n_hc} / {n_total}")
c2.metric("CHƯA ĐỦ SHEET", n_cd)
c3.metric("CHƯA NỘP", n_cn)

st.divider()

# ── Group cards ──────────────────────────────────────────────────────────────
gcols = st.columns(2)
for i, grp in enumerate(["GEE", "GEL"]):
    gdf = df[df["group"] == grp]
    if gdf.empty:
        continue
    n_g = len(gdf)
    n_g_hc = int((gdf["trang_thai"] == "Hoàn chỉnh").sum())
    pct = n_g_hc / n_g if n_g > 0 else 0.0
    grp_color = GROUP_COLORS.get(grp, "#555")

    with gcols[i]:
        st.markdown(
            f'<div style="border:1px solid #ddd;border-radius:8px;padding:16px">'
            f'<span style="font-size:18px;font-weight:700;color:{grp_color}">{grp} Group</span><br>'
            f'<span style="font-size:14px;color:#555">{n_g_hc}/{n_g} hoàn chỉnh</span>'
            f"</div>",
            unsafe_allow_html=True,
        )
        st.progress(pct)
        chips = [
            badge(str(r["ma_don_vi"]), _STATUS_COLORS.get(r["trang_thai"], STATUS_NONE_BADGE))
            for _, r in gdf.sort_values("ma_don_vi").iterrows()
        ]
        st.markdown(" ".join(chips), unsafe_allow_html=True)

st.divider()

# ── Detail table ─────────────────────────────────────────────────────────────
st.subheader("Chi tiết đơn vị")

display = df[
    ["folder_name", "file_name", "ma_don_vi", "ten_don_vi", "group",
     *_SHEET_COLS, "file_modified", "trang_thai"]
].copy()
display["file_modified"] = pd.to_datetime(display["file_modified"], errors="coerce").dt.strftime("%Y-%m-%d")
for col in _SHEET_COLS:
    display[col] = display[col].map(_sheet_icon)
display["trang_thai"] = display["trang_thai"].map({
    "Hoàn chỉnh": "🟢 Hoàn chỉnh",
    "Chưa đủ":   "🟠 Chưa đủ",
    "Chưa nộp":  "⚫ Chưa nộp",
})

display = display.rename(columns={
    "folder_name":           "Thư mục",
    "file_name":             "Tên file",
    "ma_don_vi":             "Mã đơn vị",
    "ten_don_vi":            "Tên đơn vị",
    "group":                 "Group",
    "report_status":         "Report",
    "key_drivers_status":    "Key Drivers",
    "ratio_commit_status":   "Ratio Commit",
    "adl_input_status":      "ADL Input",
    "file_modified":         "Cập nhật",
    "trang_thai":            "Trạng thái",
})

status_cols = ["Report", "Key Drivers", "Ratio Commit", "ADL Input"]
styled = display.style.map(_color_status, subset=status_cols)
st.dataframe(styled, use_container_width=True, hide_index=True)
