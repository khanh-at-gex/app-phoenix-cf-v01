# GELEX CASHPLAN — Issue Log

Add a new entry every time a bug is encountered, a workaround is applied, or unexpected behavior is observed.
This prevents the same problem from being "discovered" and re-solved in future sessions.

Format: `## #N — Short title`  
Fields: Date · File(s) · Symptom · Root cause · Fix applied · Watch for

---

## #1 — `msal` missing from requirements.txt

**Date:** ~2026-04 (commit 0eaa200)  
**File:** `requirements.txt`  
**Symptom:** Streamlit Cloud deploy failed at startup with `ModuleNotFoundError: No module named 'msal'`.  
**Root cause:** `msal` was used in `utils/data_loader.py` but was not declared in `requirements.txt`. It had been installed locally without being recorded.  
**Fix:** Added `msal` to `requirements.txt`.  
**Watch for:** Any new `import` statement — always check `requirements.txt` at the same time. Same risk applies to other implicit dependencies (e.g. `openpyxl`, `xlrd`).

---

## #2 — `st.secrets` not forwarded to `os.environ` on Streamlit Cloud

**Date:** ~2026-04 (commit ee02168)  
**File:** `app.py`, `utils/data_loader.py`  
**Symptom:** App loaded locally (`.env` file present) but crashed on Streamlit Cloud with `KeyError` on env vars (`MS_CLIENT_ID`, etc.). Secrets were set correctly in Streamlit Cloud dashboard.  
**Root cause:** `python-dotenv` loads variables from `.env` locally into `os.environ`. On Streamlit Cloud, secrets are only available via `st.secrets`, not `os.environ`, so all `os.environ.get()` calls returned `None`.  
**Fix:** Added a bridge at the top of `app.py` that iterates `st.secrets` and copies each key into `os.environ` if not already set. This makes both environments work with the same `os.environ.get()` calls.  
**Watch for:** Do not move the bridge out of `app.py`, and do not add a second copy elsewhere. If adding new env vars, add them to both `.env.example` and the Streamlit Cloud secrets dashboard.

---

## #3 — Duplicate `st.plotly_chart` key in P4 covenant tabs

**Date:** ~2026-04 (commit 06998ad)  
**File:** `pages/p4_detail.py`  
**Symptom:** Streamlit raised `DuplicateWidgetID` error when switching between covenant sub-tabs in P4. Charts rendered incorrectly or not at all on second+ tabs.  
**Root cause:** `st.plotly_chart()` was called without a `key=` argument inside a loop over covenant types. Streamlit requires unique widget keys; without them, all instances shared the same auto-generated key.  
**Fix:** Added `key=f"covenant_chart_{chi_tieu}"` to each `st.plotly_chart()` call inside the loop.  
**Watch for:** Any `st.plotly_chart`, `st.dataframe`, `st.selectbox`, or similar widget rendered inside a loop or conditional must have a unique `key=` argument. This applies to all pages, not just P4.

---

## #4 — P3 heatmap "Total" row summed all rows including subtotals

**Date:** 2026-05 (commit 1d81072)  
**File:** `pages/p3_dashboard.py`  
**Symptom:** The "Total" row in the heatmap showed inflated values — larger than the sum of all visible unit rows.  
**Root cause:** The total was computed with `df_report.groupby("period")["so_tien_tong"].sum()` without filtering by `khoan_muc`. The raw data contains rows that are header/subtotal rows in addition to CFO/CFI/CFF detail rows, causing double-counting.  
**Fix:** Added a pre-filter `df_report[df_report["khoan_muc"].isin(["CFO","CFI","CFF"])]` before computing the total row.  
**Watch for:** Any aggregation on `df_report` that is meant to represent "total cash flow" must filter to `khoan_muc in ["CFO","CFI","CFF"]`. Do not use `sum(so_tien_tong)` across all rows without this filter.

---

## #5 — P5 badges and grid invisible in Streamlit light theme

**Date:** ~2026-05 (commit 5e4fadc)  
**File:** `pages/p5_adl.py`  
**Symptom:** In light theme, CTTV badges and ADL matrix grid cells had very low contrast or were invisible (white text on white/light background, dark borders not visible).  
**Root cause:** Inline CSS used hardcoded dark background colors that worked in dark theme but not in light theme. Streamlit does not automatically invert custom HTML/CSS colors.  
**Fix:** Updated badge and grid CSS to use explicit `color` and `background-color` values that are readable in both themes (explicit dark text on colored backgrounds, explicit border colors).  
**Watch for:** Any inline HTML/CSS in Streamlit pages must be tested in both light and dark themes. Avoid relying on `currentColor` or inherited text colors for custom HTML components — always specify colors explicitly.

---

## #6 — `st.secrets → os.environ` bridge missing from `app.py`

**Date:** 2026-05-07  
**File:** `app.py`, `utils/data_loader.py`  
**Symptom:** Found during code review: `app.py` no longer contained the bridge that copies `st.secrets` into `os.environ`. Local dev still worked because `python-dotenv` loads `.env`, but a deploy to Streamlit Cloud would have crashed at import time when `utils/data_loader.py` evaluated `ROOT_DIR = os.environ["ROOT_DIR"]` before any secret was available.  
**Root cause:** Bridge was removed (or never re-added) during a previous refactor. Original fix recorded in #2 was undone.  
**Fix:** Re-added the bridge at the top of `app.py` (above all `utils.*` imports). Made `ROOT_DIR` lazy in `utils/data_loader.py` — read inside `_fetch_all()` via `os.environ.get("ROOT_DIR")` with a clear `RuntimeError` if missing.  
**Watch for:** Do not delete the bridge or move it below the `utils` imports. Do not re-introduce module-level `os.environ[...]` (bracket access) reads in `utils/`. Always use `os.environ.get(...)` per CLAUDE.md §6.

---

## #7 — P3 tab order disagreed with `requirements.md`

**Date:** 2026-05-07  
**File:** `pages/p3_dashboard.py`  
**Symptom:** Code rendered tabs in order [Heatmap, Sankey, Biểu đồ cột, Tích lũy], but `requirements.md` §3 P3 specifies Sankey first, then Heatmap, then Tích lũy. Tab 3 "Biểu đồ cột" existed in the code but was undeclared in any spec.  
**Root cause:** Tab order drifted during incremental development; documentation was not kept in sync.  
**Fix:** Reordered to [Sankey, Heatmap, Biểu đồ cột, Tích lũy]. "Biểu đồ cột" is kept (working extension feature) and now declared in `requirements.md`-aligned docs (`REPO.md` and `TODO.md`).  
**Watch for:** When adding a tab to a page, update `requirements.md` (or at minimum `REPO.md`) in the same change so the spec stays authoritative.

---

## #8 — Cross-page duplication: folder-order list, group map, badge HTML

**Date:** 2026-05-07  
**File:** `pages/p2_tracking.py`, `pages/p3_dashboard.py`, `pages/p4_detail.py`, `pages/p5_adl.py`  
**Symptom:** Same logic re-implemented in multiple pages: folder-numbered ordered unit dropdown (p3 + p4), `ma_don_vi → group` lookup (p3 + p4 + p5), `_badge()` HTML helper (p2 + p5), period-label string concat (p3 + p4), global filter session-state reads (every page).  
**Fix:** Extracted to `utils/filters.py` (`get_global_filters`, `unit_group_map`, `build_unit_label_list`, `period_label`, `apply_global_filters`) and `utils/ui.py` (`badge`). All four pages refactored to import.  
**Watch for:** Per CLAUDE.md §3, when two pages need the same filter or helper, extract to `utils/` immediately — don't let it duplicate across pages.
