import pandas as pd

# ── Group colors ─────────────────────────────────────────────────────────────
GEE_COLOR = "#4C72B0"
GEL_COLOR = "#9467bd"
GROUP_COLORS = {"GEE": GEE_COLOR, "GEL": GEL_COLOR}

# ── Status colors (file submission / covenant ok|break) ──────────────────────
STATUS_OK = "#2e7d32"
STATUS_WARN = "#f57c00"
STATUS_NONE = "#9e9e9e"

# Brighter variants used for badges
STATUS_OK_BADGE = "#28a745"
STATUS_WARN_BADGE = "#fd7e14"
STATUS_NONE_BADGE = "#6c757d"

# ── Cash-flow category colors ────────────────────────────────────────────────
KHOAN_MUC_COLORS = {"CFO": "#4C72B0", "CFI": "#55A868", "CFF": "#C44E52"}

# ── Diverging heatmap (red ← 0 → green) ──────────────────────────────────────
HEATMAP_COLORSCALE = [
    [0.00, "#8b0000"],
    [0.35, "#e74c3c"],
    [0.50, "#f5f0eb"],
    [0.65, "#27ae60"],
    [1.00, "#1a5c30"],
]


def fmt_money(v) -> str:
    """Plain 2-decimal format with thousands separator. Use in tables."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{float(v):,.2f}"


def fmt_money_short(v) -> str:
    """Shorthand: ≥1,000,000 → T, ≥1,000 → B. Use in chart annotations / KPIs."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    v = float(v)
    a = abs(v)
    if a >= 1_000_000:
        return f"{v / 1_000_000:.1f}T"
    if a >= 1_000:
        return f"{v / 1_000:.0f}B"
    return f"{v:.0f}"
