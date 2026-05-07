# REPO.md — GELEX CASHPLAN Repository Description

> This file is the authoritative AI-readable description of the repo.
> Read this file instead of re-scanning all source files.
> Keep it updated whenever architecture or page completion status changes.

---

## Project Overview

**Name:** PHOENIX: CASHPLAN Dashboard  
**Purpose:** Interactive Streamlit dashboard for GELEX conglomerate tracking projected cash flows (2026–2030) across 25+ subsidiary companies (CTTVs).  
**Business context:** Part of Project Phoenix — annual strategic planning cycle. Finance team at each CTTV submits an Excel workbook to SharePoint. This app reads those workbooks live, normalizes the data, and presents group-level and unit-level views.  
**Data unit:** All monetary values in **triệu VNĐ** (millions VND).  
**Users:** Internal GELEX finance and strategy team. No public auth — protected by `APP_PASSWORD` env var.

---

## Tech Stack

| Layer | Library/Tool | Version |
|---|---|---|
| UI framework | Streamlit | ≥1.36 |
| Charts | Plotly | ≥5.0 |
| Data manipulation | Pandas | ≥2.0 |
| Excel reading | python-calamine (via pandas `engine="calamine"`) | latest |
| SharePoint API | gex_msgraph (custom wrapper) | git main |
| Azure AD auth | msal (ConfidentialClientApplication) | latest |
| Env vars | python-dotenv | latest |
| Runtime | Python 3.x, Streamlit Cloud or local |

---

## Repository Layout

```
data_etl/
├── app.py                    # Entry point: page config, navigation, sidebar init
├── requirements.txt          # Python dependencies
├── .env                      # Live credentials — NEVER commit
├── .env.example              # Credential template
│
├── pages/
│   ├── p2_tracking.py        # P2: file submission status tracker
│   ├── p3_dashboard.py       # P3: group-level cash flow analytics
│   ├── p4_detail.py          # P4: single-CTTV deep dive
│   └── p5_adl.py             # P5: ADL strategic matrix
│
├── utils/
│   ├── data_loader.py        # SharePoint fetch + data cleaning pipeline
│   ├── sidebar.py            # Global sidebar filters + session state init
│   ├── charts.py             # Shared color constants + fmt_money / fmt_money_short
│   ├── filters.py            # get_global_filters, unit_group_map, build_unit_label_list, period_label
│   ├── ui.py                 # badge() HTML, chart_height_slider()
│   ├── breakdown_chart.py    # Shared 3-cột-CFO/CFI/CFF chart builder (P3 Bar/Total + P4 Dòng tiền)
│   ├── p3_filter_controls.py # Shared 2-row filter controls (P3 Bar + P3 Total)
│   ├── p3_sankey.py          # P3 Tab 1 — Sankey
│   ├── p3_heatmap.py         # P3 Tab 2 — Heatmap
│   ├── p3_bar.py             # P3 Tab 3 — Biểu đồ phân rã (multi-panel)
│   ├── p3_total.py           # P3 Tab 4 — Tổng hợp (single panel + cumulative)
│   └── p3_cumul.py           # P3 Tab 5 — Tích lũy (placeholder)
│
├── doc/
│   ├── companies.csv         # Registry: ma_don_vi, ten_don_vi, type, group, folder
│   └── ownership.csv         # Graph: parent → child + ownership_pct + method
│
├── tests/
│   └── test_load.py          # Standalone data pipeline smoke test
│
└── doc/
    ├── REPO.md               # ← this file
    ├── requirements.md       # Product requirements spec (authoritative)
    ├── schema_mapping.md     # Raw Excel column → snake_case mapping
    ├── TODO.md               # Task tracker
    ├── ISSUES.md             # Bug and workaround log
    └── Phoenix_Dashboard webapp_v01.1_20260428.html  # Design mockup
```

---

## Data Flow

```
SharePoint (OneDrive/Graph API)
    │
    │  gex_msgraph.GraphClient (async)
    │  ├── list files in ROOT_DIR
    │  └── download each .xls* in parallel (asyncio.gather)
    ▼
utils/data_loader.py — _fetch_all() [async]
    │  reads 4 sheets per file:
    │  Report | Key drivers | Ratio_commit | ADL input
    ▼
_clean_report() / _clean_key_drivers() / _clean_ratio_commit() / _clean_adl()
    │  → normalize column names, coerce types, parse quarters
    ▼
load_data()  [@st.cache_data ttl=3600]
    │  returns dict:
    │  { "report": df, "key_drivers": df, "ratio_commit": df,
    │    "adl": df, "summary": df }
    ▼
app.py — stores dict in st.session_state["data"]
    ▼
pages/*.py — each page reads from st.session_state["data"]
             + applies global filters from session state
```

---

## Session State Schema

Initialized in `utils/sidebar.py:init_session_state()`:

| Key | Type | Default | Set by |
|---|---|---|---|
| `data` | dict | `{}` | `app.py` after `load_data()` |
| `global_nam` | list[int] | `[2026,2027,2028,2029,2030]` | sidebar NĂM multiselect |
| `global_quy` | list[int] | `[1,2,3,4]` | sidebar QUÝ multiselect |
| `global_nhom` | str | `"Tất cả"` | sidebar NHÓM selectbox |

---

## Data Frames Reference

All columns in snake_case. See `doc/schema_mapping.md` for raw→clean mapping.

### df_report
Source sheet: `Report`  
Key columns: `code, ma_don_vi, ten_don_vi, khoan_muc, chi_tieu, nam, quy, so_tien_tong, phan_loai_on_dinh_khong_on_dinh, phan_loai_ben_trong_ben_ngoai, doi_tuong_giao_dich_kinh_te`  
Derived: `period = f"{nam}-Q{quy}"`; CF36 rows = `code.str.startswith("CF36")`

### df_key_drivers
Source sheet: `Key drivers`  
Key columns: `ma_don_vi, ten_don_vi, chi_tieu, cau_phan_value_chain, key_drivers, phan_loai_on_dinh_khong_on_dinh, phan_loai_ben_trong_ben_ngoai`  
Note: structural data — no nam/quy columns, not time-series

### df_ratio_commit
Source sheet: `Ratio_commit`  
Key columns: `ma_don_vi, ten_don_vi, chi_tieu_cam_ket, gia_tri_cam_ket, nam, quy, gia_tri_thuc_hien, status, nguon_so_lieu`  
`status` values: `"ok"` | `"break"`

### df_adl
Source sheet: `ADL input`  
Key columns: `ma_don_vi, ten_don_vi, nam, giai_doan_nganh, vi_the_canh_tranh, muc_do_tin_cay, thi_phan_uoc_tinh`  
Note: annual assessments — one row per (ma_don_vi, nam)

### df_summary
Derived (not from a sheet)  
Key columns: `folder_name, folder_path, file_name, file_modified, report_status, key_drivers_status, ratio_commit_status, adl_input_status`  
Status values: `"success"` | `"missing_sheet"` | `NaN` (no file)

---

## Pages — Current Status

### P2 — Theo dõi dữ liệu ✅ COMPLETE
- KPI cards: Hoàn chỉnh / Chưa đủ sheet / Chưa nộp
- Group cards (GEE, GEL) with progress bars and unit badges
- Detail table with 4-sheet status per unit
- Reads: `df_summary`

### P3 — Dashboard chiến lược 🔶 PARTIAL (4/5 tabs)
Orchestrator [pages/p3_dashboard.py](../pages/p3_dashboard.py) chỉ load data + dispatch sang `utils/p3_*.py`.

- **Tab 1 — Sankey dòng tiền nội bộ** ✅ ([utils/p3_sankey.py](../utils/p3_sankey.py)):
  - Mỗi link = 1 cặp `(ma_don_vi, doi_tuong_giao_dich_kinh_te)`, value = `|sum(so_tien_tong)|`
  - **VAS sign convention**: dấu `so_tien_tong` quyết định hướng arrow (Thu = counterparty → CTTV; Chi = CTTV → counterparty). Xem ISSUES #10
  - Row 1 (7 filter): Năm (multiselect) · Quý · Loại dòng (Thu/Chi/Tất cả, default Thu) · Phân loại ổn định · Phân loại Nội/Ngoại (default Bên trong) · Khoản mục · Loại giao dịch (multiselect, depend on Khoản mục)
  - Row 2 (2 filter, raw columns): Đơn vị (`ma_don_vi`) · Đối tác (`doi_tuong_giao_dich_kinh_te`) — show cả Thu lẫn Chi của đơn vị được chọn
  - **Node positions FIXED** (cumulative-value y) → annotation rơi đúng midpoint
  - Annotations giá trị trên top 10 link lớn nhất (link nhỏ xem qua hover)
  - Node labels append tổng inflow: `"GEE (2,500B)"`
  - Border container, height slider 400-800
  - Expander "🔍 Xem dữ liệu gốc" hiện 2 tab Raw rows + Aggregated pairs
- **Tab 2 — Heatmap Dòng tiền từng CT** ✅ ([utils/p3_heatmap.py](../utils/p3_heatmap.py)):
  - Units × periods colored by net CF, dynamic colorbar ticks
  - 6 filter: Đơn vị · Show theo (Năm/Quý, default Năm) · Phân loại ổn định · Nội/Ngoại · Khoản mục · Loại giao dịch (multiselect, depend on Khoản mục)
  - Folder-ordered rows, height slider 300-800
- **Tab 3 — Biểu đồ phân rã dòng tiền** ✅ ([utils/p3_bar.py](../utils/p3_bar.py)):
  - Mỗi đơn vị được chọn = 1 panel chart riêng. Mỗi period có 3 cột CFO/CFI/CFF cạnh nhau (offsetgroup); optional 2-level stack theo Ổn định/KOĐ hoặc Bên trong/Ngoài
  - "Cách phân rã theo": Không phân rã / Bên trong-Bên ngoài / Ổn định-KOĐ
  - "Kỳ" Năm/Quý · "Trục Y" Riêng/Chung
  - Số Net hiển thị ở đầu mút ngoài cột (font Arial Black, màu Khoản mục)
  - 3 panel/row (wrap), default 3 đơn vị HOLDING+SUB_HOLDING (GELEX/GEE/GEL), height slider 400-800
- **Tab 4 — Tổng hợp dòng tiền** ✅ ([utils/p3_total.py](../utils/p3_total.py)):
  - Single panel chart = sum across các đơn vị được chọn (default rỗng)
  - Same controls as Tab 3 trừ "Trục Y"; thay bằng checkbox "Hiển thị Lũy kế"
  - **Line "Tổng CF (kỳ)"** cam dotted (primary Y) + **line "Lũy kế"** xanh đen solid (secondary Y, optional)
  - height slider 400-800
- **Tab 5 — Tích lũy dư tiền** ❌ placeholder
- KPI row (4 cards above tabs) ❌ not built
- Shared utils: [utils/breakdown_chart.py](../utils/breakdown_chart.py) (chart builder), [utils/p3_filter_controls.py](../utils/p3_filter_controls.py) (filter row + apply, dùng cho cả Bar và Total)
- Reads: `df_report`, `df_summary`

### P4 — Chi tiết CTTV ✅ COMPLETE
- Page-level filters: unit dropdown + khoản mục multiselect
- Header: unit name + group badge
- Sheet status bar
- Bar+line chart (CF over time)
- CF36 Bên trong panel
- Chi tiết chỉ tiêu table
- Key Drivers table
- Covenant Tracking (sub-tabs per covenant, line chart + KPI card)
- ADL Assessment table
- Reads: all 4 DataFrames

### P5 — Ma trận ADL 🔶 PARTIAL (2/3 tabs)
- **Tab 1 — Ma trận** ✅: 5×4 HTML grid with CTTV badges per cell, color-coded by group
- **Tab 2 — Bảng tổng hợp** ✅: full table with global NĂM + NHÓM filters
- **Tab 3 — Phân bổ vốn** ❌ not built (ADL signal logic defined in requirements.md §3 P5)
- Reads: `df_adl`, `df_summary`

---

## Key Design Decisions

### ConfidentialClientApplication for Azure AD (not PublicClientApplication)
`utils/data_loader.py:_ConfidentialTokenProvider` uses MSAL's `ConfidentialClientApplication` with `acquire_token_by_username_password()`. This was necessary because `PublicClientApplication` failed with token errors in the deployed (non-interactive) environment. See `doc/ISSUES.md` issue #3.

### Async data loading wrapped in asyncio.run()
`load_data()` is synchronous (required by `@st.cache_data`) but internally calls `asyncio.run(_fetch_all())`. All SharePoint file downloads happen in parallel via `asyncio.gather()`. Do not add `await` outside `_fetch_all()`.

### Folder ordering for unit display
Units are sorted by the numeric prefix of `folder_name` (e.g. `"01. GEE"` → `1`). For folders containing multiple units (multi-unit folders), a suffix `(ma_don_vi)` is appended to disambiguate in dropdowns.

### Streamlit Cloud credential bridge
`app.py` copies `st.secrets` entries into `os.environ` at startup so that `python-dotenv` / `os.environ` calls inside `utils/` work the same locally (from `.env`) and on Streamlit Cloud (from secrets). Do not remove or move this bridge.

### Group derivation from folder number
Folders `01–13` → GEE; folders `14+` → GEL. This logic is in `utils/data_loader.py:_folder_group()`.

### Heatmap total row
The "Total" row in the P3 heatmap sums only rows where `khoan_muc` is CFO, CFI, or CFF — not all rows. This prevents double-counting header/subtotal rows present in the raw data.

### Shared util modules
Cross-page logic lives in `utils/`:
- `utils/filters.py` — `get_global_filters()`, `unit_group_map()`, `build_unit_label_list()`, `period_label()`, `apply_global_filters()`. Every page uses these instead of re-implementing locally.
- `utils/ui.py` — `badge(text, color)` HTML helper for chip-style badges.
- `utils/charts.py` — color constants (GEE/GEL/STATUS/KHOAN_MUC), `HEATMAP_COLORSCALE`, and two formatters: `fmt_money()` (2-decimal, for tables) and `fmt_money_short()` (B/T shorthand, for chart annotations and KPI cards).

### Plotly Scatter offsetgroup workaround (numeric x)
`go.Scatter` không support `offsetgroup` trên `xaxis.type="category"` — Plotly treat numeric x là category mới. Workaround dùng trong P3 Tab 3 + P4 Dòng tiền:
- Convert period x sang numeric index `0, 1, 2, ...`
- Dot/label x = `index + KM_OFFSET[km]` (CFO=−0.267, CFI=0, CFF=+0.267 ứng với bargap=0.2)
- xaxis: `tickmode="array"`, `tickvals=x_numeric`, `ticktext=periods_sorted`

Bars cũng dùng numeric x để Plotly bargroup auto-spread. Xem ISSUES #9.

### Sankey VAS sign convention
P3 Tab Sankey: hướng mũi tên đi theo HƯỚNG TIỀN CHẢY THẬT, không phải hướng báo cáo. Theo VAS: `so_tien_tong > 0` = thu (CTTV nhận), `< 0` = chi (CTTV trả). Source/target được swap theo dấu trước khi build Sankey. Xem ISSUES #10.

### Shared breakdown chart logic
P3 Tab 3 và P4 "Dòng tiền theo thời gian" có cùng pattern (3 cột CFO/CFI/CFF/period + optional Level 2 stack + outer-end labels). Logic chung trong [utils/breakdown_chart.py](../utils/breakdown_chart.py): `BREAKDOWN_OPTIONS`, `KM_OFFSET`, `STACK_COL`, `CAT_ORDER`, `compute_periods()`, `resolve_breakdown()`, `compute_label_y_offset()`, `add_breakdown_panel()`.

### Lazy ROOT_DIR
`utils/data_loader.py` does NOT read `ROOT_DIR` at import time. It reads inside `_fetch_all()` via `os.environ.get("ROOT_DIR")` and raises a clear `RuntimeError` if missing. This avoids import-time crashes when the env var hasn't been bridged from `st.secrets` yet.

---

## Colors & Branding

```python
GEE_COLOR  = "#4C72B0"   # blue
GEL_COLOR  = "#9467bd"   # purple
STATUS_OK  = "#2e7d32"   # green (hoàn chỉnh / ok)
STATUS_WARN = "#f57c00"  # orange (chưa đủ / break)
STATUS_NONE = "#9e9e9e"  # grey (chưa nộp)
```

Defined in `utils/charts.py`. Do not redefine inline in page files.

---

## What Is NOT Yet Built

- P3 Tab 4: Tích lũy dư tiền (cumulative cash)
- P3 KPI row (4 metric cards above tabs)
- P5 Tab 3: Phân bổ vốn (ADL signal → capital allocation table)
- Phase 6 polish: sidebar load warnings, empty-state messages
- P1 Tổng quan (deferred indefinitely per requirements.md)
