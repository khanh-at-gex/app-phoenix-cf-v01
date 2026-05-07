# CLAUDE.md — AI Working Instructions for GELEX CASHPLAN

This file governs how any AI assistant must behave when working in this repository.
Read it completely before touching any file.

---

## 1. Mandatory Workflow — Plan Before Every Change

**No code change may be made without explicit user approval.**

Follow this sequence for every task, no matter how small:

1. **Read** — read the relevant files and understand current state
2. **Plan** — describe what you intend to change and why
3. **Propose** — list every file that will be created, edited, or deleted as a numbered task list
4. **Wait** — stop and wait for the user to reply with approval (or corrections)
5. **Execute** — only after approval, make changes one task at a time
6. **Update docs** — after execution, update `doc/TODO.md` and `doc/REPO.md` if anything architectural changed; append to `doc/ISSUES.md` if a bug was encountered

Never batch steps 4 and 5. Never proceed past step 3 on the assumption that the user will approve.

---

## 2. After Every Session

Always do all three at the end of any session that changed code:

- **`doc/TODO.md`** — mark completed items ✓, add any new tasks discovered
- **`doc/REPO.md`** — update the "Current Status" section if page completion status changed; update "Key Design Decisions" if a new pattern was introduced
- **`doc/ISSUES.md`** — append a new entry for every bug, unexpected behavior, or workaround applied, even minor ones

---

## 3. Code Standards

### Language
- All Python logic, variable names, column names: **English / snake_case**
- All UI labels, messages shown to users: **Vietnamese** (as per existing convention)
- Column names follow `doc/schema_mapping.md` exactly — do not rename or alias

### Naming
| Thing | Convention | Example |
|---|---|---|
| Page files | `p{N}_{slug}.py` | `p3_dashboard.py` |
| Utility modules | descriptive noun | `data_loader.py`, `charts.py` |
| Functions | `snake_case` verb phrases | `load_data()`, `fmt_money()` |
| Classes | `PascalCase` | `_ConfidentialTokenProvider` |
| Constants | `UPPER_CASE` | `GEE_COLOR`, `GEL_COLOR` |
| Local variables | `snake_case` | `df_filtered`, `unit_list` |

### File Size & Structure
- Page files: max ~400 lines; split helpers into `utils/` if reused across pages
- Keep rendering logic (Streamlit widgets, charts) in page files; keep data logic in `utils/`
- Do not duplicate filtering logic — if two pages need the same filter, extract to `utils/`

### Comments
- Default: **no comments**
- Add a comment only when the WHY is non-obvious: a workaround, a hidden constraint, a subtle invariant
- Never describe what the code does — the code itself does that

### Formatting
- 4-space indentation (no tabs)
- Max line length: 100 characters
- UTF-8 encoding for all `.py` files

---

## 4. Data & DataFrame Rules

- Never mutate a cached DataFrame — always work on a copy: `df = df_source.copy()`
- Column names come from `doc/schema_mapping.md`; never invent new column names on the fly
- Numeric money values are in **triệu VNĐ** — do not silently scale or re-scale
- The `so_tien_tong` column is signed (negative = outflow) — preserve the sign
- Period label format: `"{nam}-Q{quy}"` (e.g. `"2026-Q1"`) — used as a display and sort key

---

## 5. Streamlit Rules

- Use `@st.cache_data(ttl=3600)` only in `utils/data_loader.py` — never add caching inside page files
- Never call `st.rerun()` inside a loop or a cached function
- Session state keys are initialized in `utils/sidebar.py:init_session_state()` — do not initialize the same key elsewhere
- Use `st.columns`, `st.tabs`, `st.expander` for layout; avoid excessive nesting of containers
- Every `st.plotly_chart()` call must have a unique `key=` argument to avoid duplicate-key errors

---

## 6. Security Rules

- Never commit `.env` or any file containing real credentials
- Never hardcode credentials, tokens, or passwords in source code
- Use `os.environ.get("VAR")` to read env vars — never `os.environ["VAR"]` (raises on missing)
- The Streamlit Cloud bridge (`st.secrets` → `os.environ`) lives in `app.py` — do not duplicate it

---

## 7. Forbidden Patterns

- ❌ Blocking synchronous I/O inside `@st.cache_data` functions
- ❌ `st.rerun()` inside a loop
- ❌ Hardcoded unit lists — derive from data
- ❌ `df["col"]` without checking the column exists first if reading from external/untrusted data
- ❌ Duplicate Plotly chart keys across tabs
- ❌ Adding `msal` or other packages without updating `requirements.txt`

---

## 8. Key References

| File | Purpose |
|---|---|
| `doc/REPO.md` | Full repo description — read this before asking questions about architecture |
| `doc/requirements.md` | Product requirements spec — authoritative on what each page must do |
| `doc/schema_mapping.md` | Column name mappings from raw Excel → snake_case |
| `doc/TODO.md` | Task tracker — what is done, in progress, and planned |
| `doc/ISSUES.md` | Bug and issue log — read before starting any fix to avoid repeating solved problems |
