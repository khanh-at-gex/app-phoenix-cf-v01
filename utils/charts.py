import pandas as pd

GEE_COLOR = "#4C72B0"
GEL_COLOR = "#9467bd"
GROUP_COLORS = {"GEE": GEE_COLOR, "GEL": GEL_COLOR}


def fmt_money(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{float(v):,.2f}"
