"""Shared filter / lookup helpers used by every page."""
from __future__ import annotations

import pandas as pd
import streamlit as st


def get_global_filters() -> tuple[list[int], list[int], str]:
    """Read NĂM / QUÝ / NHÓM ĐƠN VỊ from session state with safe defaults."""
    nam_list = [int(x) for x in st.session_state.get("global_nam", list(range(2026, 2031)))]
    quy_list = [int(x) for x in st.session_state.get("global_quy", [1, 2, 3, 4])]
    nhom = st.session_state.get("global_nhom", "Tất cả")
    return nam_list, quy_list, nhom


def unit_group_map(df_summary: pd.DataFrame) -> dict[str, str]:
    """ma_don_vi → group ('GEE' / 'GEL')."""
    src = df_summary[df_summary["ma_don_vi"].notna() & df_summary["group"].notna()]
    return (
        src[["ma_don_vi", "group"]]
        .drop_duplicates()
        .set_index("ma_don_vi")["group"]
        .to_dict()
    )


def build_unit_label_list(
    df_summary: pd.DataFrame,
    units: set[str] | None = None,
) -> tuple[list[str], dict[str, str]]:
    """
    Folder-numbered ordered labels for unit dropdowns.
    Multi-unit folders get a ' — {ma_don_vi}' suffix to disambiguate.
    Pass `units` to restrict to only units present in your data.
    Returns (ordered_labels, label_to_unit).
    """
    df = df_summary[
        df_summary["folder_name"].notna()
        & ~df_summary["folder_name"].str.startswith("00")
        & df_summary["ma_don_vi"].notna()
    ]
    if units is not None:
        df = df[df["ma_don_vi"].isin(units)]

    df = df[["folder_name", "ma_don_vi"]].drop_duplicates().sort_values("folder_name")
    if df.empty:
        return [], {}

    fc = df["folder_name"].value_counts()
    df = df.copy()
    df["label"] = df.apply(
        lambda r: r["folder_name"]
        if fc[r["folder_name"]] == 1
        else f"{r['folder_name']} — {r['ma_don_vi']}",
        axis=1,
    )
    return df["label"].tolist(), dict(zip(df["label"], df["ma_don_vi"]))


def period_label(df: pd.DataFrame) -> pd.Series:
    """'YYYY-QN' when quy is present, else 'YYYY'."""
    base = df["nam"].astype(str)
    mask = df["quy"].notna()
    if mask.any():
        return base.where(~mask, df["nam"].astype(str) + "-Q" + df["quy"].astype(str))
    return base


def apply_global_filters(
    df: pd.DataFrame,
    nam_list: list[int],
    quy_list: list[int],
) -> pd.DataFrame:
    """Filter df by global NĂM / QUÝ. Rows with NA quy pass through (annual data)."""
    quy_mask = df["quy"].isna() | df["quy"].isin(quy_list)
    return df[df["nam"].isin(nam_list) & quy_mask].copy()
