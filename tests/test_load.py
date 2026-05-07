"""Standalone data pipeline test.

Run from project root:
    python tests/test_load.py
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path

# Force UTF-8 stdout so Vietnamese column names print correctly on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Add project root to sys.path so 'utils' is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.data_loader import (  # noqa: E402
    _build_summary,
    _clean_adl,
    _clean_key_drivers,
    _clean_ratio_commit,
    _clean_report,
    _fetch_all,
    _run_async,
)

SEP = "=" * 65

print(SEP)
print("GELEX CASHPLAN — Data pipeline test")
print(SEP)

t0 = time.time()
print("\n[1] Fetching from SharePoint …")
df_list_files, paths, df_report_raw, df_kd_raw, df_rc_raw, df_adl_raw = _run_async(
    _fetch_all()
)
print(f"    Done in {time.time() - t0:.1f}s")

print(f"\n[2] File inventory")
print(f"    Excel files found: {len(paths)}")
print(f"    Folders in scope:  {len(df_list_files)}")

print(f"\n[3] Raw shapes (before clean)")
print(f"    Report       : {df_report_raw.shape}")
print(f"    Key drivers  : {df_kd_raw.shape}")
print(f"    Ratio commit : {df_rc_raw.shape}")
print(f"    ADL input    : {df_adl_raw.shape}")

print(f"\n[4] Cleaning …")
df_report = _clean_report(df_report_raw)
df_kd = _clean_key_drivers(df_kd_raw)
df_rc = _clean_ratio_commit(df_rc_raw)
df_adl = _clean_adl(df_adl_raw)

print(f"    Report       : {df_report.shape}  cols={list(df_report.columns)}")
print(f"    Key drivers  : {df_kd.shape}  cols={list(df_kd.columns)}")
print(f"    Ratio commit : {df_rc.shape}  cols={list(df_rc.columns)}")
print(f"    ADL input    : {df_adl.shape}  cols={list(df_adl.columns)}")

print(f"\n[5] Units in Report: {sorted(df_report['ma_don_vi'].dropna().unique().tolist())}")

print(f"\n[6] Building summary …")
df_summary = _build_summary(
    df_list_files, paths,
    df_report_raw, df_kd_raw, df_rc_raw, df_adl_raw,
    df_report, df_kd,
)

show = df_summary[~df_summary["folder_name"].str.startswith("00")][
    ["folder_name", "ma_don_vi", "group",
     "report_status", "key_drivers_status", "ratio_commit_status", "adl_input_status"]
]
print(show.to_string(index=False))

print(f"\n[7] Status counts")
for col in ["report_status", "key_drivers_status", "ratio_commit_status", "adl_input_status"]:
    counts = df_summary[col].value_counts(dropna=False).to_dict()
    print(f"    {col}: {counts}")

print(f"\n{SEP}")
print(f"All done in {time.time() - t0:.1f}s total  ✓")
print(SEP)
