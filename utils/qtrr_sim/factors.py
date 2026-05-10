"""Driver universe derivation for P6 manual sensitivity tab.

The "driver" universe is built from `df_key_drivers.key_drivers` (free-text
Vietnamese) by deduplication. Each unique string becomes one driver; its
default mode (Common/Separate) is inferred from how many subs mention it.
"""
from __future__ import annotations

import pandas as pd


_COLS = [
    "driver", "n_subs", "n_lines", "default_mode",
    "mode", "shock_pct", "elasticity", "lag", "include",
]


def derive_driver_universe(df_kd_scoped: pd.DataFrame) -> pd.DataFrame:
    """Build the driver list from df_key_drivers (already scoped to selected subs).

    Returns DataFrame with columns:
        driver        unique key_drivers string
        n_subs        # distinct ma_don_vi mentioning this driver
        n_lines       # rows mentioning this driver
        default_mode  "Common" if n_subs >= 2 else "Separate"
        mode          editable; initialized = default_mode
        elasticity    editable; default 1.0
        include       editable; default True
    Sorted by n_lines desc.
    """
    if df_kd_scoped.empty or "key_drivers" not in df_kd_scoped.columns:
        return pd.DataFrame(columns=_COLS)

    df = df_kd_scoped[df_kd_scoped["key_drivers"].notna()].copy()
    df["key_drivers"] = df["key_drivers"].astype(str).str.strip()
    df = df[df["key_drivers"] != ""]
    df = df[df["ma_don_vi"].notna()]
    if df.empty:
        return pd.DataFrame(columns=_COLS)

    grouped = (
        df.groupby("key_drivers")
        .agg(n_subs=("ma_don_vi", "nunique"), n_lines=("chi_tieu", "count"))
        .reset_index()
        .rename(columns={"key_drivers": "driver"})
    )
    grouped["default_mode"] = grouped["n_subs"].apply(
        lambda n: "Common" if n >= 2 else "Separate"
    )
    grouped["mode"] = grouped["default_mode"]
    grouped["shock_pct"] = 0
    grouped["elasticity"] = 1.0
    grouped["lag"] = 0
    grouped["include"] = True
    return (
        grouped.sort_values("n_lines", ascending=False)
        .reset_index(drop=True)[_COLS]
    )


def driver_to_subs(df_kd_scoped: pd.DataFrame, driver: str) -> list[str]:
    """Return the sorted list of ma_don_vi linked to a given driver string."""
    if df_kd_scoped.empty or "key_drivers" not in df_kd_scoped.columns:
        return []
    df = df_kd_scoped[df_kd_scoped["key_drivers"].notna()]
    df = df[df["key_drivers"].astype(str).str.strip() == driver]
    return sorted(df["ma_don_vi"].dropna().astype(str).unique().tolist())
