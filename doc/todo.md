# GELEX CASHPLAN — Task Tracker

Format: `[x]` done · `[ ]` pending · `[~]` in progress  
Update this file at the end of every AI session.

---

## Completed

### Phase 0 — Project Setup
- [x] Create `requirements.txt` with core dependencies
- [x] Create `utils/` directory and package init
- [x] Add `msal` to requirements.txt (was missing initially — see ISSUES.md #1)
- [x] Add `python-calamine` for fast Excel reading
- [x] Configure `.gitignore` (`.env`, Excel files, `__pycache__`, test files, OS files)
- [x] Bridge `st.secrets` → `os.environ` in `app.py` for Streamlit Cloud deploy (see ISSUES.md #2)
- [x] Add `APP_PASSWORD` gate in `app.py`

### Phase 1 — Skeleton
- [x] `app.py` — wide layout, app title, sidebar global filters, page navigation with `st.navigation()`
- [x] `utils/data_loader.py` — async SharePoint load, `@st.cache_data(ttl=3600)`, returns 5-key dict
- [x] `utils/sidebar.py` — session state init, NĂM/QUÝ/NHÓM filters, "Làm mới dữ liệu" button
- [x] `utils/charts.py` — GEE/GEL colors, `fmt_money()`
- [x] Stub pages for P2–P5

### Phase 2 — P2 Theo dõi dữ liệu
- [x] KPI row: 3 metric cards (Hoàn chỉnh / Chưa đủ sheet / Chưa nộp)
- [x] Group cards (GEE, GEL) with progress bar and unit badge chips
- [x] Detail table with ✓/✗ for all 4 sheets + Trạng thái badge
- [x] Filter: exclude folders starting with "00"
- [x] Apply global NHÓM ĐƠN VỊ filter

### Phase 3 — P3 Dashboard chiến lược (partial)
- [x] Tab 2 — Heatmap: units × periods, RdYlGn colorscale, cell annotations, dynamic sizing
- [x] Heatmap in-tab filters: on_dinh, noi_ngoai, khoan_muc, unit multiselect
- [x] Heatmap folder-ordered rows (by numeric folder prefix)
- [x] Heatmap Total row: sums CFO+CFI+CFF only (fixed from all-rows bug — see ISSUES.md #4)

### Phase 4 — P4 Chi tiết CTTV
- [x] Page-level filters: unit dropdown (folder-ordered, with suffix for multi-unit folders) + khoản mục multiselect
- [x] Header: unit name, group badge
- [x] Sheet status bar
- [x] Bar+line chart "Dòng tiền theo thời gian"
- [x] CF36 Bên trong panel (right column)
- [x] Chi tiết chỉ tiêu table (df_report filtered)
- [x] Key Drivers table (df_key_drivers filtered)
- [x] Covenant Tracking: sub-tabs per chi_tieu_cam_ket, line chart actual vs threshold, KPI card
- [x] ADL Assessment table (df_adl filtered)
- [x] Fix duplicate `st.plotly_chart` key in covenant tabs (see ISSUES.md #3)
- [x] Reorder P4 columns per UX feedback

### Phase 5 — P5 Ma trận ADL (partial)
- [x] Tab 1 — Ma trận: 5×4 HTML grid with CTTV badges per cell
- [x] Tab 1 — Badge color by group (GEE blue, GEL purple)
- [x] Tab 1 — Year selector and NHÓM filter
- [x] Tab 2 — Bảng tổng hợp: full table with NĂM + NHÓM filters
- [x] Fix P5 light theme rendering issues (see ISSUES.md #5)

### Infrastructure / UX
- [x] App title ("PHOENIX: CASHPLAN Dashboard") displayed above navigation
- [x] Grouped bar chart mode for P4 time-series
- [x] Plain number format (removed locale-dependent formatting)
- [x] Optimize data loading (parallel downloads via `asyncio.gather`)

---

## In Progress

- [x] P3 Tab 1 — Sankey nội bộ CF36 (3-level Plotly Sankey with 6 in-tab filters)
- [x] P3 Tab 3 — Biểu đồ cột (3-panel GEX/GEE/GEL grouped/stacked bar — extension beyond requirements.md)
- [~] P3 Tab 4 — Tích lũy dư tiền (not started — placeholder tab exists)
- [~] P5 Tab 3 — Phân bổ vốn (not started — placeholder tab exists)

## Refactor (2026-05)

- [x] Restore `st.secrets → os.environ` bridge in `app.py` (regression — see ISSUES.md #6)
- [x] Make `ROOT_DIR` lazy in `utils/data_loader.py`; move local `import io / asyncio / GraphClient` to module top
- [x] Reorder P3 tabs to match requirements.md (Sankey, Heatmap, Bar, Cumul)
- [x] Add `key=` to P4 time-series Plotly chart
- [x] Expand `utils/charts.py`: STATUS_OK/WARN/NONE, KHOAN_MUC_COLORS, HEATMAP_COLORSCALE, `fmt_money_short()`
- [x] New `utils/filters.py`: `get_global_filters`, `unit_group_map`, `build_unit_label_list`, `period_label`, `apply_global_filters`
- [x] New `utils/ui.py`: `badge()` HTML helper
- [x] Refactor p2/p3/p4/p5 to use the new utils (drop duplicated folder-order, group-map, period-label, badge code)
- [x] Move `test_load.py` → `tests/test_load.py`; replace hardcoded `d:\...` path with `Path(__file__).parent.parent`

## Refactor pass 2 (2026-05-07)

- [x] Add `companies.csv` + `ownership.csv` registries (placeholder values, finance team to fill)
- [x] Add P2 detail table column "Tên file"
- [x] Sankey logic rewrite: source = `ma_don_vi`, target = `doi_tuong_giao_dich_kinh_te`; arrow direction theo VAS sign; "Loại dòng" Thu/Chi/Tất cả filter; Khoản mục → Loại giao dịch dependency; reorder 7 filter cột
- [x] Heatmap: thêm "Show theo" Năm/Quý filter; "Đơn vị" filter đầu; "Loại giao dịch" depend on Khoản mục
- [x] P3 Bar tab "Biểu đồ phân rã dòng tiền": multi-select đơn vị (mỗi đơn vị = 1 panel); 2-level breakdown (CFO/CFI/CFF × Ổn định-Bên trong); outer-end Net labels; Trục Y Riêng/Chung; bỏ "Loại biểu đồ" toggle, bỏ "Tổng" line
- [x] Height slider 400-800 cho tất cả chart P3 + P4
- [x] Sankey border container + font Inter
- [x] P4 "Dòng tiền theo thời gian" đồng bộ với P3 phân rã (cùng 3 cột CFO/CFI/CFF + 2-level breakdown)
- [x] Phase A — Extract shared chart logic: `utils/breakdown_chart.py`, `chart_height_slider()`
- [x] Phase B — Split P3: `utils/p3_sankey.py`, `utils/p3_heatmap.py`, `utils/p3_bar.py`, `utils/p3_cumul.py`. `pages/p3_dashboard.py` còn 67 lines (orchestrator)
- [x] Phase C — Update REPO.md, ISSUES.md (#9, #10), todo.md

### TODO — phase D (defer cho đến khi finance team confirm số ownership)
- [ ] Wire `doc/companies.csv` vào `data_loader.py` (replace `_folder_group()` heuristic)
- [ ] Wire `doc/ownership.csv` vào `data_loader.py` cho consolidation
- [ ] P3 Bar default `_DEFAULT_PANEL_UNITS` thay từ hardcode `["GELEX", "GEE", "GEL"]` sang query `companies.type.isin(["HOLDING", "SUB_HOLDING"])`

## Refactor pass 3 (2026-05-08)

- [x] P3 Sankey: VAS-correct arrow direction (swap source/target by `sign(so_tien_tong)`); annotations giá trị trên link với fixed node positions; node labels include tổng inflow
- [x] P3 Sankey row 2: filter Đơn vị (`ma_don_vi`) + Đối tác (`doi_tuong`) → company-centric view (xem cả Thu/Chi của 1 DN)
- [x] Loại giao dịch → multiselect cho cả 3 tab Sankey/Heatmap/Bar (đã đồng bộ với multiselect Heatmap có sẵn)
- [x] `fmt_money_short`: cap tại B (tỷ), không dùng T. ≥100B → integer, 1B-100B → 1 decimal
- [x] **New tab "Tổng hợp dòng tiền"** ([utils/p3_total.py](../utils/p3_total.py)): single panel sum-across + Tổng CF line (primary Y) + Lũy kế line (secondary Y, toggleable)
- [x] Extract [utils/p3_filter_controls.py](../utils/p3_filter_controls.py) — shared 2-row controls + filter logic. P3 Bar và P3 Total dùng chung, save ~80 lines duplicate
- [x] Đổi P3 Bar wrap từ 2/row → **3/row** (default 3 panels GELEX/GEE/GEL khít 1 hàng)
- [x] P2: cột "Tên file" cuối bảng, bỏ cột "Group", `Cập nhật` format `YYYY-MM-DD HH:MM:SS` GMT+7

---

## Pending

### Phase 3 — P3 remaining
- [ ] KPI row (4 metric cards above tabs): net CF total, CF36 Bên trong, CTTV count, period count
- [x] Tab 1 — Sankey:
  - [x] Build node list: CTTV names → GEE/GEL → GELEX
  - [x] Build link list from CF36 Bên trong rows
  - [x] Render `go.Sankey` with in-tab filters
- [ ] Tab 4 — Tích lũy dư tiền:
  - [ ] Group by period, compute net CF + cumulative sum
  - [ ] Render bar+line combo chart
  - [ ] Display toggle: Tổng hợp / Ổn định/KOĐ / Stacked bar
  - [ ] Alert banner when cumulative first exceeds 100B

### Phase 5 — P5 remaining
- [ ] Tab 3 — Phân bổ vốn:
  - [ ] Map (vi_the_canh_tranh, giai_doan_nganh) → ADL signal using lookup table in requirements.md
  - [ ] Table with Signal badge (Invest=green, Hold=grey, Harvest=yellow, Divest=red)
  - [ ] Capital weight column (proportional to Invest units)

### Phase 6 — Polish
- [x] Number formatter shorthand: ≥1,000,000 → T, ≥1,000 → B (added as `fmt_money_short()` in `utils/charts.py`; `fmt_money()` retained for tables)
- [ ] Sidebar warning if any unit has non-success, non-missing_sheet status
- [ ] `st.spinner` while data loads on first run
- [ ] Empty-state messages when filters return no data
- [ ] Full integration test with all 25+ CTTV files loaded
- [ ] Consistent color theme audit across all charts and badges
