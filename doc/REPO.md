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
│   ├── p5_adl.py             # P5: ADL strategic matrix
│   └── p6_simulation.py      # P6: manual driver-shock sensitivity
│
├── utils/
│   ├── data_loader.py        # SharePoint fetch + data cleaning pipeline
│   ├── sidebar.py            # Global sidebar filters + session state init
│   ├── charts.py             # Shared color constants + fmt_money / fmt_money_short
│   ├── filters.py            # get_global_filters, unit_group_map, build_unit_label_list, period_label
│   ├── ui.py                 # badge() HTML, chart_height_slider()
│   ├── breakdown_chart.py    # Shared 3-cột-CFO/CFI/CFF chart builder (P3 Bar/Total + P4 Dòng tiền)
│   ├── p3_filter_controls.py # Shared 2-row filter controls (P3 Bar + P3 Total)
│   ├── p3_sankey_common.py   # Shared filter + agg + VAS swap (Sankey Plotly)
│   ├── p3_sankey.py          # P3 Tab — Sankey (Plotly)
│   ├── p3_heatmap.py         # P3 Tab — Heatmap
│   ├── p3_pivot.py           # P3 Tab — Bảng pivot (HTML table với rowspan)
│   ├── p3_bar.py             # P3 Tab — Biểu đồ phân rã (multi-panel + line Tổng CF)
│   ├── p3_total.py           # P3 Tab — Tổng hợp (single panel + cumulative)
│   ├── p3_cumul.py           # P3 Tab — Tích lũy (placeholder)
│   └── qtrr_sim/             # P6 simulation engines
│       ├── __init__.py
│       ├── factors.py        #   driver universe (dedup key_drivers, default mode)
│       └── manual.py         #   manual sensitivity engine + Streamlit render
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

### P3 — Dashboard chiến lược 🔶 PARTIAL (5/6 tabs)
Orchestrator [pages/p3_dashboard.py](../pages/p3_dashboard.py) chỉ load data + dispatch sang `utils/p3_*.py`. Tất cả chart tabs có **`Cỡ chữ`** segmented control (Nhỏ 0.85× / Vừa 1.0× / Lớn 1.25× / Rất lớn 1.5×) và **`Chiều cao`** slider 300–800px.

- **Tab 1 — Sankey (Plotly)** ✅ ([utils/p3_sankey.py](../utils/p3_sankey.py)):
  - Mỗi link = 1 cặp `(ma_don_vi, doi_tuong_giao_dich_kinh_te)`, value = `|sum(so_tien_tong)|`
  - **VAS sign convention**: dấu `so_tien_tong` quyết định hướng arrow (Thu = counterparty → CTTV; Chi = CTTV → counterparty). Xem ISSUES #10
  - Filter row 1 (7 control): Năm (multiselect) · Quý · Loại dòng (Thu/Chi/Tất cả, default Thu) · Phân loại ổn định · Phân loại Nội/Ngoại (default Bên trong) · Khoản mục · Loại giao dịch (multiselect, depend on Khoản mục)
  - Filter row 2 (company-centric): **Đơn vị** dùng folder-mapped labels giống P4 (`"01. GELEX"`, `"23. BSG2 — DA07"`) · **Đối tác** dùng raw `doi_tuong_giao_dich_kinh_te` (vì counterparty external có thể không có folder mapping). Show cả Thu lẫn Chi của đơn vị được chọn
  - Filter + agg + VAS swap qua [utils/p3_sankey_common.py](../utils/p3_sankey_common.py)
  - **Node positions FIXED** (cumulative-value y) → annotation rơi đúng midpoint
  - Annotations giá trị trên top 10 link lớn nhất (link nhỏ xem qua hover); node labels append tổng inflow `"GEE (2,500B)"`
  - Border container; expander "🔍 Xem dữ liệu gốc" với raw + aggregated pairs
- **Tab 2 — Heatmap Dòng tiền từng CT** ✅ ([utils/p3_heatmap.py](../utils/p3_heatmap.py)):
  - Units × periods colored by net CF, dynamic colorbar ticks
  - 6 filter: Đơn vị · Show theo (Năm/Quý, default Năm) · Phân loại ổn định · Nội/Ngoại · Khoản mục · Loại giao dịch (multiselect, depend on Khoản mục)
  - Folder-ordered rows
- **Tab 3 — Bảng pivot** ✅ ([utils/p3_pivot.py](../utils/p3_pivot.py)):
  - HTML table render với `<td rowspan>` merge cột Đơn vị (`st.dataframe` không support cell merge)
  - Filter giống Heatmap (Đơn vị **folder-mapped** giống P4, Show theo, Ổn định, Nội/Ngoại, Khoản mục, Loại giao dịch)
  - Display options: **Hiển thị Net** (tổng per đơn vị), **Conditional format** (sign color + Net bg), **Đơn vị Triệu/Tỷ** (data ÷ 1,000)
  - **Phân rã thêm theo** multiselect 3 options (Đối tác / Ổn định / Nội/Ngoại) — chọn 0+ để add row levels. Sub-rows lặp + Loại giao dịch rowspan = số sub-rows. Net row colspan = `1 + n_extras`
  - Cột **"Tổng"** cuối bảng = row sum across periods (nền vàng)
  - Net rows: bold, nền xanh nhạt; conditional format: âm đỏ / dương xanh lá
- **Tab 4 — Biểu đồ phân rã dòng tiền** ✅ ([utils/p3_bar.py](../utils/p3_bar.py)):
  - Mỗi đơn vị được chọn = 1 panel chart riêng. Mỗi period có 3 cột CFO/CFI/CFF cạnh nhau (offsetgroup); optional 2-level stack theo Ổn định/KOĐ hoặc Bên trong/Ngoài
  - "Cách phân rã theo": Không phân rã / Bên trong-Bên ngoài / Ổn định-KOĐ · "Kỳ" Năm/Quý · "Trục Y" Riêng/Chung
  - Số Net ngoài cột (font Arial Black, màu Khoản mục) + **line "Tổng CF"** cam dotted per panel
  - 3 panel/row (wrap), default 3 đơn vị HOLDING+SUB_HOLDING (GELEX/GEE/GEL)
  - **Subplot frame** cho mỗi panel (`mirror=True` axis lines), `horizontal_spacing=0.03` để 3 chart sát nhau hơn
- **Tab 5 — Tổng hợp dòng tiền** ✅ ([utils/p3_total.py](../utils/p3_total.py)):
  - Single panel chart = sum across các đơn vị được chọn (default rỗng)
  - Same controls as Tab 5 trừ "Trục Y"; thay bằng checkbox "Hiển thị Lũy kế"
  - **Line "Tổng CF (kỳ)"** cam dotted (primary Y) + **line "Lũy kế"** xanh đen solid (secondary Y, optional)
- **Tab 6 — Tích lũy dư tiền** ❌ placeholder
- KPI row (4 cards above tabs) ❌ not built
- Shared utils:
  - [utils/breakdown_chart.py](../utils/breakdown_chart.py) — bar chart builder cho Bar + Total
  - [utils/p3_filter_controls.py](../utils/p3_filter_controls.py) — filter row + apply cho Bar + Total
  - [utils/p3_sankey_common.py](../utils/p3_sankey_common.py) — filter + VAS swap cho Sankey Plotly
  - [utils/ui.py](../utils/ui.py) — `chart_height_slider`, `chart_font_scale`
- Reads: `df_report`, `df_summary`

### P4 — Chi tiết CTTV ✅ COMPLETE
- Page-level filters: unit dropdown (folder-mapped labels) + khoản mục multiselect
- Header: unit name + group badge
- Sheet status bar
- "Dòng tiền theo thời gian" chart (uses `add_breakdown_panel` từ [utils/breakdown_chart.py](../utils/breakdown_chart.py)): 3 cột CFO/CFI/CFF mỗi period + optional Level 2 stack + line "Tổng CF" cam dotted (sum CFO+CFI+CFF) + outer-end Net labels
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

### P6 — Mô phỏng dòng tiền ✅ COMPLETE (Manual sensitivity)
Slider-driven multivariate "what-if" tool for a manually-chosen group of CTTVs. **Result-first layout** (since 2026-05-11): KPI/charts appear at top of viewport; driver controls in a collapsed expander at the bottom.

- **Scope (collapsed expander)**: multiselect đơn vị (folder-mapped labels) · Năm/Quý multiselect · `cash_0` number_input. Label preview shows `{n_units} đơn vị · Cash₀ = …` so user sees state without expanding
- **Driver universe**: built via [utils/qtrr_sim/factors.py](../utils/qtrr_sim/factors.py) `derive_driver_universe()` (dedup `key_drivers` free-text, default `mode = "Common" if n_subs >= 2 else "Separate"`)
- **Driver editor** (`st.data_editor`): per-driver `mode | elasticity | lag | include`. Editor key includes a hash of the driver list so changing the group cleanly resets stale state. No longer carries `shock_pct` — sliders are the single source of truth for shock magnitude
- **Sliders** (-50% to +100%, step 1%, stored as fraction): **Common** = 1 slider shared across subs (key `p6_d__{drv}__*`); **Separate** = 1 slider per `(driver × ma_don_vi)` (key `p6_d__{drv}__{sub}`); **Override** (include=False) = 1 slider per `(driver × selected_unit)` regardless of mapping. **Reset shock** button clears slider keys only — mode/ε/lag config is preserved
- **Engine** ([utils/qtrr_sim/manual.py](../utils/qtrr_sim/manual.py)): `compute_shocked_cf()` left-joins df_report ↔ df_key_drivers on `(ma_don_vi, chi_tieu)`, sums `elasticity × delta` per linked driver, multiplies baseline by `(1 + shock_factor)`. Restricted to `khoan_muc ∈ {CFO, CFI, CFF}`. Lag shifts per-(sub, chi_tieu) baseline by N periods before applying shock
- **Layout** (top → bottom): Scope expander (collapsed) → **Driver controls expander "🎚️ Điều chỉnh kịch bản"** (collapsed) → Scenario Summary banner → "4️⃣ Kết quả" header + period_mode toggle → KPI strip → Floor input → Charts → Pivot/Decomposition/Detail expanders
- **Outputs**:
  - Scenario Summary banner (auto-generated 1-liner: "🔥 Driver +X% · …" when active; info "💡 Chưa áp dụng shock…" when all sliders = 0)
  - Compact KPI strip (7 metrics: Tổng CF gốc / Sau shock / Δ Tổng / Δ Min cash + Δ CFO/CFI/CFF)
  - Cash floor input + breach alert
  - KM chart (CFO/CFI/CFF panels: bars Gốc vs Sau + lines Lũy kế)
  - Period bar chart (Gốc grey vs Shocked blue, grouped) + Cumulative cash line chart side-by-side (auto-height; chart_height_slider removed)
  - Comparison Pivot table (HTML rowspan, mirrors [utils/p3_pivot.py](../utils/p3_pivot.py))
  - Decomposition table — per-driver Δ contribution sorted by `|contribution|` desc, with **Total row** (nền đậm) + **data bar** diverging (zero-centered, đỏ/xanh) on driver rows only
  - Audit expander with row-level shocked dataframe
- **Invariants** (verified by smoke test): all sliders 0 → `shocked == baseline`; `Σ decomposition.contribution == Σ shocked.delta`
- Reads: `df_report`, `df_key_drivers`, `df_summary`

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
P3 Tab Biểu đồ phân rã + Tổng hợp + P4 "Dòng tiền theo thời gian" có cùng pattern (3 cột CFO/CFI/CFF/period + optional Level 2 stack + outer-end labels). Logic chung trong [utils/breakdown_chart.py](../utils/breakdown_chart.py): `BREAKDOWN_OPTIONS`, `KM_OFFSET`, `STACK_COL`, `CAT_ORDER`, `compute_periods()`, `resolve_breakdown()`, `compute_label_y_offset()`, `add_breakdown_panel()`. P3 Bar tab thêm line "Tổng CF" mỗi panel.

### Shared Sankey filter + agg
P3 Sankey (Plotly) dùng [utils/p3_sankey_common.py](../utils/p3_sankey_common.py) làm filter + VAS swap helper: `render_sankey_filters_and_prepare()` trả về `SankeyData(sk, agg, sk_loai)`. Caller render Plotly Sankey từ `agg`. (ECharts variant đã removed — A/B test kết thúc, giữ Plotly.)

### Font scale + chart height controls
[utils/ui.py](../utils/ui.py): `chart_height_slider(key, default, min, max)` slider 300-800px; `chart_font_scale(key)` segmented control 4 mức (Nhỏ 0.85× / Vừa 1.0× / Lớn 1.25× / Rất lớn 1.5×). Áp dụng cho tất cả chart tabs trong P3 + P4.

### `fmt_money_short` cap tại B (tỷ)
[utils/charts.py](../utils/charts.py): không dùng "T" (nghìn tỷ) — user yêu cầu so sánh dễ hơn ở đơn vị B. Quy tắc: ≥100B → integer with comma (e.g. `2,500B`); 1B–100B → 1 decimal (e.g. `21.5B`); <1B → raw triệu.

### Pivot table HTML rendering
[utils/p3_pivot.py](../utils/p3_pivot.py): dùng `st.markdown(html, unsafe_allow_html=True)` với `<table><td rowspan>...</td></table>` vì `st.dataframe` không support cell merge cần thiết để hiển thị "Excel-style" hierarchy (Đơn vị merged across multi-row chi_tieu groups). 3-level rowspan khi bật "Phân rã theo Đối tác".

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
- P6 Monte Carlo: triangular drivers + Iman-Conover correlation + fan chart + tornado (qtrr-sim V1 spec — deferred)
- Phase 6 polish: sidebar load warnings, empty-state messages
- P1 Tổng quan (deferred indefinitely per requirements.md)
