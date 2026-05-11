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

## Refactor pass 4 (2026-05-08) — A/B test ECharts

- [x] New tab "Sankey (ECharts)" ([utils/p3_sankey_echarts.py](../utils/p3_sankey_echarts.py)) song song với tab Plotly để A/B compare
- [x] ECharts loaded qua CDN `echarts@5.5.0` (`st.components.v1.html`) — không cần Python wrapper (`streamlit-echarts` v0.6 không tương thích với Streamlit 1.55 components.v2)
- [x] Same VAS swap, same filter UI, session keys `p3_ec_*` (độc lập với `p3_sk_*`)
- [x] Native ECharts features: draggable nodes, edge labels trên mỗi link, gradient line, hover adjacency
- [x] GELEX node hardcode màu đỏ `#c0392b` (HOLDING)
- [x] Edge labels prepend "→" để chỉ direction (ECharts không có native arrowhead; graphic.elements positioning fragile)
- [ ] **A/B decision pending** — sau khi user test:
  - (a) Giữ Plotly, drop ECharts tab
  - (b) Switch sang ECharts hoàn toàn — replace `utils/p3_sankey.py`
  - (c) Giữ cả 2 (không khuyến nghị)

## Refactor pass 5 (2026-05-08) — Pivot tab + features + share more

### New features
- [x] **New tab "Bảng pivot"** ([utils/p3_pivot.py](../utils/p3_pivot.py)) — HTML table với rowspan merge cột Đơn vị
  - Filter giống Heatmap (Đơn vị raw, Show theo, Ổn định, Nội/Ngoại, Khoản mục, Loại giao dịch)
  - Display options: Hiển thị Net, Conditional format, Đơn vị Triệu/Tỷ, Phân rã theo Đối tác
  - Cột "Tổng" cuối bảng (= row sum), Net rows per đơn vị (bold + bg)
- [x] **`chart_font_scale()`** ([utils/ui.py](../utils/ui.py)) — segmented control Nhỏ/Vừa/Lớn/Rất lớn, áp dụng cho tất cả P3 chart tabs
- [x] **`fmt_money_short`** cap tại B (tỷ), không dùng T
- [x] P3 Bar tab thêm **line "Tổng CF"** (line + dot) per panel
- [x] Sankey: "Loại giao dịch" multiselect; row 2 filter Đơn vị/Đối tác (raw); arrow direction VAS-correct
- [x] Heatmap: "Show theo" Năm/Quý filter

### Refactor (extract shared)
- [x] [utils/p3_sankey_common.py](../utils/p3_sankey_common.py) — extract filter row 1 + row 2 + apply + VAS swap (~120 lines duplicate giữa Plotly và ECharts Sankey)
- [x] [utils/p3_sankey.py](../utils/p3_sankey.py): refactor dùng `render_sankey_filters_and_prepare()` (347 → ~210 lines)
- [x] [utils/p3_sankey_echarts.py](../utils/p3_sankey_echarts.py): refactor dùng common helper (310 → ~180 lines)
- [x] [utils/p3_pivot.py](../utils/p3_pivot.py): cleanup signature — bỏ unused `ordered_labels` / `label_to_unit` args (dùng raw `ma_don_vi`)
- [x] [pages/p3_dashboard.py](../pages/p3_dashboard.py): update `render_pivot()` call

### Doc sync
- [x] [doc/REPO.md](../doc/REPO.md): layout block + 7-tab section rewrite + Key Design Decisions (Sankey common, font scale, fmt_money_short B-only, Pivot HTML render)
- [x] [doc/todo.md](../doc/todo.md): pass 4 + 5 entries

### Pivot tab pass 5b (cùng ngày)
- [x] Bảng pivot: thay checkbox "Phân rã theo Đối tác" thành **multiselect 3 options** (Đối tác / Ổn định / Nội/Ngoại) — chọn 0+ levels
- [x] Đơn vị filter trong P3 Pivot + Sankey row 2: chuẩn hoá dùng `ordered_labels` (folder-mapped, giống P4) — nhất quán với Heatmap/Bar/Total
- [x] Đối tác filter trong Sankey row 2: giữ raw vì counterparty external có thể không có folder mapping
- [x] Ký pháp: `render_sankey_filters_and_prepare()` add `ordered_labels`/`label_to_unit` params; `p3_pivot.render()` restore signature

### Pivot pass 5c
- [x] Bảng pivot: dòng cuối **TỔNG CỘNG (Σ Net)** = sum tất cả Net rows; styling đậm (nền `#2c3e50`, chữ trắng)
- [x] Bảng pivot: compact rows (font 12px, padding 3×8, line-height 1.2) — ~30% shorter

### P4 + P3 Bar pass 5d
- [x] P4 "Dòng tiền theo thời gian": thêm line "Tổng CF" (cam dotted, lines+markers) — đồng bộ với P3 Bar
- [x] P3 "Biểu đồ phân rã dòng tiền": subplot frame qua `mirror=True` axis lines + giảm `horizontal_spacing` 0.08→0.03 + `vertical_spacing` 0.18→0.12 → 3 panels sát nhau hơn, có viền rõ
- [x] P3 Bar: subplot titles to hơn (`16px` × font_scale, `family="Arial Black"`) + `yshift=14` đẩy lên cao hơn — top margin bump 80→90

## Phase 7 — P6 Mô phỏng dòng tiền (manual sensitivity, 2026-05-11)

- [x] New `utils/qtrr_sim/` package (`__init__.py`, `factors.py`, `manual.py`)
- [x] `factors.derive_driver_universe(df_kd_scoped)` → DataFrame `(driver, n_subs, n_lines, default_mode, mode, elasticity, include)`. Default `mode = "Common" if n_subs >= 2 else "Separate"`
- [x] `manual.compute_shocked_cf(...)` engine — left-join report ↔ key_drivers on (ma_don_vi, chi_tieu); supports Common (single δ) and Separate (per-sub δ) drivers with per-driver elasticity and include flag
- [x] `manual.aggregate_per_period`, `cumulative_cash`, `decomposition_table` (per-driver Δ contribution, sorted by |Δ| desc)
- [x] `pages/p6_simulation.py` orchestrator — single page, 5-step UX (Phạm vi → Phân loại Driver → Sliders → Kết quả → Audit)
- [x] Comparison Pivot table (HTML rowspan, mirrors p3_pivot.py): segmented "Hiển thị" mode (Δ / Gốc / Shock / Cả ba), "Hiển thị Chỉ tiêu" multiselect, Triệu/Tỷ toggle, per-unit Net + TỔNG CỘNG row
- [x] Period bar chart (Gốc vs Shocked grouped) + Cumulative cash line chart (with optional sàn tiền hline)
- [x] Driver editor (`st.data_editor`) keyed by hash of driver list — group change cleanly resets stale state; warns when slider count > 30
- [x] Smoke test (synthetic fixtures): zero-shock invariant, common +10%, separate per-sub, decomposition sums to total Δ
- [x] Wire `app.py` nav (P6 = Mô phỏng, icon 🎚️)
- [x] Update `doc/REPO.md` (P6 section + layout + What Is NOT Yet Built)

### Phase 7 — Pending (V1.1 deferred)
- [ ] P6 Tab 2 — Monte Carlo engine per qtrr-sim V1 spec (triangular drivers, Iman-Conover correlation, fan chart, tornado, deterministic scenarios). Will reuse the same driver universe + elasticity editor from manual mode

## Phase 8 — Cleanup + P6 polish (2026-05-11)

- [x] **Drop P3 Sankey (ECharts) tab** — A/B test concluded, keeping Plotly. Removed `utils/p3_sankey_echarts.py`; updated `pages/p3_dashboard.py` (6 tabs → 5 + Tích lũy placeholder); doc sync (REPO.md tab numbering)
- [x] P6 UX refactor — chart-first layout: driver editor + CF/Drivers reference moved into "🛠️ Cài đặt nâng cao" expander (collapsed); pivot moved into "📊 Xem bảng số liệu" expander; decomposition moved into "📋 Phân rã đóng góp Driver" expander; Period bar + Cumulative line side-by-side
- [x] P6 Cash floor breach alert — banner above CFO/CFI/CFF section (✅ green or ⚠️ red with first-breach period); red-marker overlay on cumulative chart at every breaching period; supports negative floor
- [x] P6 Reset button — 🔄 Reset paired with Step 3 subheader, zeros all `p6_d__*` session_state keys + `st.rerun()`

## Phase 9 — P6 result-first refactor (2026-05-11)

- [x] **T0** — Decomposition table: thêm dòng "Σ Tổng" (nền đậm, chữ trắng) + cải thiện data bar (đỏ/xanh tăng saturation, `align="zero"`, vmin/vmax từ driver rows only)
- [x] **T1** — Đảo layout: dùng `st.container()` placeholder cho results_slot ở đầu; KPI/charts/pivot/decomp/detail render INSIDE results_slot; driver controls expander đóng mặc định + render visually ở cuối trang. Engine vẫn chạy trước render, period_mode pre-read từ session_state
- [x] **T2** — Thống nhất UX slider: bỏ cột `shock_pct` khỏi `st.data_editor`; bỏ logic bidirectional sync slider ↔ editor (slider là single source of truth); bỏ checkbox "Hiện cột nâng cao" (luôn hiện mode/elasticity/lag/include); Reset button chỉ clear sliders, không touch mode/ε/lag config
- [x] **T3** — `Phạm vi mô phỏng & Số dư đầu kỳ` collapse vào expander mặc định; label expander gồm preview `{n_units} đơn vị · Cash₀ = ...` để xem state mà không cần mở
- [x] **T4** — Scenario Summary banner: helper `_render_scenario_summary()` auto-gen 1 dòng "🔥 Driver +X% · …" khi có shock; banner xám info "💡 Chưa áp dụng shock…" khi tất cả slider = 0; ngầm bao gồm cả non-default ε/lag overrides
- [x] **T5** — Bỏ hoàn toàn `chart_height_slider()` calls (KM/Period/Cumulative/Pivot); hardcode 380/420/420/480; remove import từ `utils.ui`

## Phase 10 — P3 Heatmap row order fix (2026-05-11)

- [x] P3 Heatmap: row order theo thứ tự user chọn trong filter Đơn vị (sel_units), không tự sort folder order. Fallback về folder order khi filter rỗng. ([utils/p3_heatmap.py](../utils/p3_heatmap.py))

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
