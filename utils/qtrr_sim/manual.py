"""P6 — Mô phỏng thủ công (manual sensitivity engine + Streamlit render).

Pure-pandas/NumPy/Plotly. No new dependencies. Reads df_report (signed flows in
triệu VNĐ) and df_key_drivers (driver-to-line mapping); takes user input for
driver shocks, elasticities, and opening cash.
"""
from __future__ import annotations

import hashlib

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from utils.charts import KHOAN_MUC_COLORS, fmt_money_short
from utils.filters import build_unit_label_list, get_global_filters
from utils.qtrr_sim.factors import derive_driver_universe


_KM_FILTER = ["CFO", "CFI", "CFF"]
_KM_ORDER = ["CFO", "CFI", "CFF"]
_MAX_SLIDERS = 30


# ─── Page-wide unit (Triệu / Tỷ) ────────────────────────────────────────────
def _unit_div() -> float:
    """Divisor to convert engine values (triệu) → display unit."""
    return 1000.0 if st.session_state.get("p6_unit_global", "Tỷ") == "Tỷ" else 1.0


def _unit_lbl() -> str:
    """Lowercase Vietnamese label of the current display unit."""
    return "tỷ" if st.session_state.get("p6_unit_global", "Tỷ") == "Tỷ" else "triệu"


def _fmt_unit(v, sign: bool = False) -> str:
    """Format a triệu-valued number in the current page unit."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    div = _unit_div()
    decimals = 1 if div == 1000.0 else 0
    fmt = ("{:+,." if sign else "{:,.") + str(decimals) + "f}"
    return fmt.format(float(v) / div)

_DEFAULT_UNIT_LABELS = [
    "24. TTP — TTP",
    "24. TTP — DA5",
    "24. TTP — DA10",
    "24. TTP — DA12",
]


def _current_shock_pct(drv: str) -> int:
    """Mirror current slider state for `drv` so the driver editor can display
    it read-only. Common drivers store under `p6_d__{drv}__*`; Separate /
    Override drivers store one key per (driver, sub). When multiple keys exist
    we surface the average — a single-number summary is the simplest UX for a
    table cell; sliders below remain the source of truth."""
    prefix = f"p6_d__{drv}__"
    common_key = f"{prefix}*"
    if common_key in st.session_state:
        try:
            return int(st.session_state[common_key])
        except (TypeError, ValueError):
            pass
    vals: list[int] = []
    for k, v in st.session_state.items():
        if not k.startswith(prefix) or k == common_key:
            continue
        try:
            vals.append(int(v))
        except (TypeError, ValueError):
            pass
    if not vals:
        return 0
    return int(round(sum(vals) / len(vals)))


# ─────────────────────────────────────────────────────────────────────────────
# Pure-data engine (testable, no Streamlit)
# ─────────────────────────────────────────────────────────────────────────────


def _period_str(nam, quy, mode: str) -> str:
    if mode == "Quý":
        return f"{int(nam)}-Q{int(quy)}"
    return str(int(nam))


def _period_sort_key(p: str) -> tuple[int, int]:
    if "-Q" in p:
        y, q = p.split("-Q")
        return (int(y), int(q))
    return (int(p), 0)


def compute_shocked_cf(
    df_report_scoped: pd.DataFrame,
    df_kd_scoped: pd.DataFrame,
    driver_specs: pd.DataFrame,
    driver_deltas: dict[tuple[str, str | None], float],
) -> pd.DataFrame:
    """Apply driver % shocks + per-driver time lag, line-by-line.

    For each row in df_report_scoped (already filtered to selected sub × period
    × CFO/CFI/CFF), find the drivers linked via df_kd_scoped on
    (ma_don_vi, chi_tieu) and combine elasticity * delta:
      - include=True + Common: shared delta keyed by (driver, None)
      - include=True + Separate: per-sub delta keyed by (driver, sub)
      - include=False: per-sub delta (override) keyed by (driver, sub)

    Lag (in quarters, signed integer per driver) shifts the baseline of each
    affected line by N periods before applying the % shock. Positive lag =
    delay (flow appears later); negative = accelerate. If a line is linked
    to multiple drivers, the FIRST driver in the kd iteration wins for lag.
    """
    cols_out = [
        "ma_don_vi", "chi_tieu", "khoan_muc", "nam", "quy",
        "baseline", "shock_factor", "lag", "lagged_baseline", "shocked", "delta",
    ]
    base = df_report_scoped[df_report_scoped["khoan_muc"].isin(_KM_FILTER)].copy()
    if base.empty:
        return pd.DataFrame(columns=cols_out)
    base["baseline"] = base["so_tien_tong"].astype(float)

    shock_lookup: dict[tuple[str, str], float] = {}
    lag_lookup: dict[tuple[str, str], int] = {}
    if not df_kd_scoped.empty and not driver_specs.empty:
        spec_by_driver = driver_specs.set_index("driver")[
            ["mode", "elasticity", "include", "lag"]
        ].to_dict(orient="index")
        kd = df_kd_scoped[df_kd_scoped["key_drivers"].notna()].copy()
        kd["key_drivers"] = kd["key_drivers"].astype(str).str.strip()
        kd = kd[(kd["key_drivers"] != "") & kd["ma_don_vi"].notna()]
        for _, row in kd.iterrows():
            sub = str(row["ma_don_vi"])
            ct = str(row["chi_tieu"])
            drv = row["key_drivers"]
            spec = spec_by_driver.get(drv)
            if not spec:
                continue
            # Lag: first driver linked to this (sub, ct) wins
            if (sub, ct) not in lag_lookup:
                try:
                    lag_lookup[(sub, ct)] = int(spec.get("lag") or 0)
                except (TypeError, ValueError):
                    lag_lookup[(sub, ct)] = 0
            # Shock: sum across all linked drivers
            use_mapping = bool(spec.get("include", True))
            elast = float(spec.get("elasticity") or 0.0)
            if use_mapping and spec.get("mode") == "Common":
                delta = float(driver_deltas.get((drv, None), 0.0))
            else:
                delta = float(driver_deltas.get((drv, sub), 0.0))
            shock_lookup[(sub, ct)] = (
                shock_lookup.get((sub, ct), 0.0) + elast * delta
            )

    keys = list(zip(base["ma_don_vi"].astype(str), base["chi_tieu"].astype(str)))
    keys_s = pd.Series(keys, index=base.index)
    base["shock_factor"] = keys_s.map(shock_lookup).fillna(0.0)
    base["lag"] = keys_s.map(lag_lookup).fillna(0).astype(int)

    # Apply lag: shift baseline within each (sub, ct) group along time axis.
    base = base.sort_values(["ma_don_vi", "chi_tieu", "nam", "quy"]).reset_index(drop=True)

    def _shift_baseline(s: pd.Series) -> pd.Series:
        lag_val = int(base.loc[s.index[0], "lag"])
        if lag_val == 0:
            return s
        return s.shift(lag_val, fill_value=0.0)

    base["lagged_baseline"] = base.groupby(
        ["ma_don_vi", "chi_tieu"]
    )["baseline"].transform(_shift_baseline)

    base["shocked"] = base["lagged_baseline"] * (1.0 + base["shock_factor"])
    base["delta"] = base["shocked"] - base["baseline"]
    return base[cols_out]


def aggregate_per_period(
    shocked: pd.DataFrame, period_mode: str = "Quý"
) -> pd.DataFrame:
    """Sum baseline / shocked / delta per period across all subs and chi_tieu."""
    if shocked.empty:
        return pd.DataFrame(columns=["period", "baseline", "shocked", "delta"])
    df = shocked.copy()
    df["period"] = [
        _period_str(n, q, period_mode)
        for n, q in zip(df["nam"], df["quy"])
    ]
    out = df.groupby("period", as_index=False)[["baseline", "shocked", "delta"]].sum()
    out["_sk"] = out["period"].map(_period_sort_key)
    return out.sort_values("_sk").drop(columns="_sk").reset_index(drop=True)


def aggregate_per_period_per_km(
    shocked: pd.DataFrame, period_mode: str = "Quý"
) -> pd.DataFrame:
    """Sum baseline / shocked / delta per (period, khoan_muc)."""
    cols = ["period", "khoan_muc", "baseline", "shocked", "delta"]
    if shocked.empty:
        return pd.DataFrame(columns=cols)
    df = shocked.copy()
    df["period"] = [
        _period_str(n, q, period_mode)
        for n, q in zip(df["nam"], df["quy"])
    ]
    out = df.groupby(
        ["period", "khoan_muc"], as_index=False
    )[["baseline", "shocked", "delta"]].sum()
    out["_sk"] = out["period"].map(_period_sort_key)
    return out.sort_values(["khoan_muc", "_sk"]).drop(columns="_sk").reset_index(drop=True)


def cumulative_cash(per_period: pd.DataFrame, cash_0: float) -> pd.DataFrame:
    """Cumulative cash trajectory starting from cash_0."""
    if per_period.empty:
        return pd.DataFrame(columns=["period", "baseline_cum", "shocked_cum"])
    df = per_period.copy()
    df["baseline_cum"] = float(cash_0) + df["baseline"].cumsum()
    df["shocked_cum"] = float(cash_0) + df["shocked"].cumsum()
    return df[["period", "baseline_cum", "shocked_cum"]]


def decomposition_table(
    df_report_scoped: pd.DataFrame,
    df_kd_scoped: pd.DataFrame,
    driver_specs: pd.DataFrame,
    driver_deltas: dict[tuple[str, str | None], float],
) -> pd.DataFrame:
    """Per-driver Δ contribution: Σ (baseline_line × elasticity × applicable_delta)."""
    cols = [
        "driver", "mode", "delta_pct_avg", "lag", "elasticity",
        "baseline_sum", "contribution", "pct_of_total",
    ]
    if driver_specs.empty:
        return pd.DataFrame(columns=cols)

    base = df_report_scoped[df_report_scoped["khoan_muc"].isin(_KM_FILTER)].copy()
    base["baseline"] = base["so_tien_tong"].astype(float)
    base_sum = (
        base.groupby(["ma_don_vi", "chi_tieu"], as_index=False)["baseline"].sum()
    )
    bk: dict[tuple[str, str], float] = {
        (str(r["ma_don_vi"]), str(r["chi_tieu"])): float(r["baseline"])
        for _, r in base_sum.iterrows()
    }

    if df_kd_scoped.empty:
        kd = pd.DataFrame(columns=["ma_don_vi", "chi_tieu", "key_drivers"])
    else:
        kd = df_kd_scoped[df_kd_scoped["key_drivers"].notna()].copy()
        kd["key_drivers"] = kd["key_drivers"].astype(str).str.strip()
        kd = kd[(kd["key_drivers"] != "") & kd["ma_don_vi"].notna()]

    rows = []
    for _, spec in driver_specs.iterrows():
        drv = spec["driver"]
        use_mapping = bool(spec.get("include", True))
        mode = spec.get("mode") or spec.get("default_mode") or "Common"
        elast = float(spec.get("elasticity") or 0.0)
        try:
            lag_val = int(spec.get("lag") or 0)
        except (TypeError, ValueError):
            lag_val = 0
        linked = kd[kd["key_drivers"] == drv]
        baseline_sum = 0.0
        contribution = 0.0
        deltas_used = []
        for _, lr in linked.iterrows():
            sub = str(lr["ma_don_vi"])
            ct = str(lr["chi_tieu"])
            row_baseline = bk.get((sub, ct), 0.0)
            baseline_sum += row_baseline
            if use_mapping and mode == "Common":
                delta = float(driver_deltas.get((drv, None), 0.0))
            else:
                delta = float(driver_deltas.get((drv, sub), 0.0))
            deltas_used.append(delta)
            contribution += row_baseline * elast * delta
        delta_avg = (sum(deltas_used) / len(deltas_used)) if deltas_used else 0.0
        rows.append({
            "driver": drv,
            "mode": (mode if use_mapping else "Override"),
            "delta_pct_avg": delta_avg * 100.0,
            "lag": lag_val,
            "elasticity": elast,
            "baseline_sum": baseline_sum,
            "contribution": contribution,
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=cols)
    total = float(out["contribution"].sum())
    out["pct_of_total"] = (
        (out["contribution"] / total * 100.0) if total != 0 else 0.0
    )
    return (
        out.sort_values("contribution", key=lambda s: s.abs(), ascending=False)
        .reset_index(drop=True)[cols]
    )


# ─────────────────────────────────────────────────────────────────────────────
# Streamlit render
# ─────────────────────────────────────────────────────────────────────────────


def render(
    *,
    df_report: pd.DataFrame,
    df_key_drivers: pd.DataFrame,
    df_summary: pd.DataFrame,
) -> None:
    """Main P6 entry point."""
    nam_g, quy_g, _ = get_global_filters()
    units_in_report = set(df_report["ma_don_vi"].dropna().astype(str).unique())
    ordered_labels, label_to_unit = build_unit_label_list(
        df_summary, units=units_in_report
    )

    # ── Step 1: Scope (collapsed expander; primary result-first layout) ────
    if "p6_cash_0" not in st.session_state:
        st.session_state["p6_cash_0"] = 0.0
    n_units_state = len(st.session_state.get("p6_units", []) or [])
    cash_0_state = float(st.session_state.get("p6_cash_0", 0.0) or 0.0)
    scope_label = (
        f"📐 Phạm vi mô phỏng & Số dư đầu kỳ "
        f"· {n_units_state} đơn vị · Cash₀ = {fmt_money_short(cash_0_state)}"
    )
    with st.expander(scope_label, expanded=False):
        sc1, sc2, sc3, sc4 = st.columns([4, 2, 2, 2])
        with sc1:
            default_units = [lb for lb in _DEFAULT_UNIT_LABELS if lb in ordered_labels]
            if not default_units:
                default_units = (
                    ordered_labels[:3] if len(ordered_labels) >= 3 else ordered_labels
                )
            sel_unit_labels = st.multiselect(
                "Đơn vị tham gia hợp nhất",
                ordered_labels,
                default=default_units,
                key="p6_units",
            )
        sel_units = [label_to_unit[lb] for lb in sel_unit_labels]

        nam_options = sorted(df_report["nam"].dropna().astype(int).unique().tolist())
        quy_options = sorted(df_report["quy"].dropna().astype(int).unique().tolist())
        with sc2:
            nam_sel = st.multiselect(
                "Năm", nam_options,
                default=[n for n in nam_g if n in nam_options] or nam_options,
                key="p6_nam",
            )
        with sc3:
            quy_sel = st.multiselect(
                "Quý", quy_options,
                default=[q for q in quy_g if q in quy_options] or quy_options,
                key="p6_quy",
            )
        with sc4:
            cash_0 = st.number_input(
                "Số dư tiền đầu kỳ (triệu VNĐ)",
                step=1000.0, format="%.0f", key="p6_cash_0",
            )

    if not sel_units:
        st.info("Mở **📐 Phạm vi mô phỏng** ở trên và chọn ít nhất một đơn vị.")
        return
    if not nam_sel or not quy_sel:
        st.info("Mở **📐 Phạm vi mô phỏng** ở trên và chọn ít nhất một Năm và một Quý.")
        return

    # ── Step 2: Consolidate ────────────────────────────────────────────────
    df_report_scoped = df_report[
        df_report["ma_don_vi"].astype(str).isin(sel_units)
        & df_report["nam"].isin(nam_sel)
        & df_report["quy"].isin(quy_sel)
        & df_report["khoan_muc"].isin(_KM_FILTER)
    ].copy()
    df_kd_scoped = df_key_drivers[
        df_key_drivers["ma_don_vi"].astype(str).isin(sel_units)
    ].copy()

    drivers_df = derive_driver_universe(df_kd_scoped)
    n_subs = len(sel_units)
    n_chi_tieu = df_report_scoped["chi_tieu"].nunique()
    n_drivers = len(drivers_df)
    st.caption(
        f"📦 **{n_subs}** đơn vị · **{n_chi_tieu}** khoản chi tiêu · "
        f"**{n_drivers}** drivers tiềm năng"
    )

    if df_report_scoped.empty:
        st.info("Không có dữ liệu báo cáo cho phạm vi đã chọn.")
        return

    if drivers_df.empty:
        st.warning(
            "Không có driver nào được khai báo cho nhóm này — bảng sẽ chỉ "
            "hiển thị baseline (Δ = 0)."
        )
        _render_baseline_only(df_report_scoped, cash_0)
        return

    # ── Driver controls expander (collapsed by default; renders BEFORE results) ─
    driver_deltas: dict[tuple[str, str | None], float] = {}
    with st.expander(
        "🎚️ Điều chỉnh kịch bản (Drivers)", expanded=False
    ):
        st.caption(
            "💡 **Kéo thanh trượt** để chỉnh % Shock cho mỗi driver. "
            "Tinh chỉnh **Loại** (Common/Separate), **Áp dụng** (override), "
            "**Elasticity**, **Lag** ngay trong bảng bên dưới."
        )

        if drivers_df.empty:
            edited = drivers_df
        else:
            editor_init = drivers_df[
                ["driver", "n_subs", "n_lines", "mode",
                 "elasticity", "lag", "include"]
            ].copy()
            # Read-only mirror of the slider state below. For Common drivers
            # this is the single slider value; for Separate/Override it's the
            # average of per-sub slider values (which is the simplest one-number
            # summary). Sliders remain the source of truth.
            editor_init["shock_pct"] = editor_init["driver"].map(_current_shock_pct)
            # Re-key the editor whenever the driver set changes so stale widget
            # state from a previous group selection doesn't bleed in.
            fp = hashlib.md5(
                "|".join(sorted(drivers_df["driver"].tolist())).encode("utf-8")
            ).hexdigest()[:8]
            editor_key = f"p6_drivers_editor_{fp}"

            edited = st.data_editor(
                editor_init,
                key=editor_key,
                hide_index=True,
                use_container_width=True,
                column_order=["driver", "n_subs", "n_lines", "mode",
                              "shock_pct", "elasticity", "lag", "include"],
                column_config={
                    "driver": st.column_config.TextColumn("Driver", disabled=True),
                    "n_subs": st.column_config.NumberColumn(
                        "# Đơn vị", disabled=True),
                    "n_lines": st.column_config.NumberColumn(
                        "# Lines", disabled=True),
                    "mode": st.column_config.SelectboxColumn(
                        "Loại", options=["Common", "Separate"], required=True,
                        help="Common = 1 thanh kéo dùng chung. Separate = "
                             "1 thanh kéo cho mỗi đơn vị có mapping driver.",
                    ),
                    "shock_pct": st.column_config.ProgressColumn(
                        "% Shock", min_value=-50, max_value=100, format="%d%%",
                        help="Chỉ hiển thị — kéo thanh trượt bên dưới để chỉnh. "
                             "Separate/Override hiển thị trung bình per-đơn vị. "
                             "Bar fill = vị trí trên dải −50%…+100%.",
                    ),
                    "elasticity": st.column_config.NumberColumn(
                        "Elasticity", min_value=-5.0, max_value=5.0,
                        step=0.1, format="%.2f",
                    ),
                    "lag": st.column_config.NumberColumn(
                        "Lag (quý)", min_value=-8, max_value=8, step=1,
                        format="%+d",
                        help="Dịch dòng tiền linked đi N quý. + = trễ "
                             "(lùi sau), − = sớm (đẩy lên trước).",
                    ),
                    "include": st.column_config.CheckboxColumn(
                        "Áp dụng", default=True,
                        help="Tick = áp dụng theo Loại (Common/Separate). "
                             "Bỏ tick = override, hiện 1 thanh kéo cho TẤT "
                             "CẢ đơn vị đã chọn (kể cả không có mapping).",
                    ),
                },
            )

        # data_editor may return None/NaN for unedited cells in some Streamlit
        # versions; coerce so equality checks downstream don't silently drop rows.
        if not edited.empty:
            edited = edited.copy()
            edited["include"] = edited["include"].fillna(False).astype(bool)
            edited["mode"] = edited["mode"].fillna("Common").astype(str)
            edited.loc[~edited["mode"].isin(["Common", "Separate"]), "mode"] = "Common"
            edited["elasticity"] = pd.to_numeric(
                edited["elasticity"], errors="coerce"
            ).fillna(1.0)
            edited["lag"] = pd.to_numeric(
                edited["lag"], errors="coerce"
            ).fillna(0).astype(int)

        if edited.empty:
            st.info("Không có driver để mô phỏng.")
            _render_baseline_only(df_report_scoped, cash_0)
            return

        # Slider buckets
        common_drivers = edited[
            (edited["mode"] == "Common") & edited["include"]
        ]["driver"].tolist()
        sep_mapped_drivers = edited[
            (edited["mode"] == "Separate") & edited["include"]
        ]["driver"].tolist()
        sep_all_drivers = edited[~edited["include"]]["driver"].tolist()

        n_common = len(common_drivers)
        n_sep_mapped = sum(
            df_kd_scoped[df_kd_scoped["key_drivers"] == d]["ma_don_vi"].nunique()
            for d in sep_mapped_drivers
        )
        n_sep_all = len(sep_all_drivers) * len(sel_units)
        n_total = n_common + int(n_sep_mapped) + int(n_sep_all)
        if n_total > _MAX_SLIDERS:
            st.warning(
                f"Số slider hiện tại = **{n_total}**, vượt quá khuyến nghị "
                f"({_MAX_SLIDERS}). Đổi sang *Common* hoặc tick *Áp dụng* "
                "để gọn hơn."
            )

        # Sliders header + Reset
        hc1, hc2 = st.columns([5, 1])
        with hc1:
            st.markdown("##### Thanh kéo")
        with hc2:
            if st.button(
                "🔄 Reset shock", use_container_width=True,
                help="Đặt lại tất cả thanh kéo % Shock về 0 (giữ nguyên "
                     "Loại / Elasticity / Lag / Áp dụng trong bảng).",
                key="p6_reset_sliders",
            ):
                # Slider session_state keys only (mode/elasticity/lag config
                # in the editor is intentionally preserved across reset).
                for k in list(st.session_state.keys()):
                    if k.startswith("p6_d__"):
                        st.session_state[k] = 0
                st.rerun()

        if common_drivers:
            st.markdown("**🟢 Drivers chung** _(áp dụng cho tất cả đơn vị)_")
            cols = st.columns(3)
            for i, drv in enumerate(common_drivers):
                slider_key = f"p6_d__{drv}__*"
                if slider_key not in st.session_state:
                    st.session_state[slider_key] = 0
                with cols[i % 3]:
                    pct = st.slider(
                        drv, min_value=-50, max_value=100, step=1,
                        format="%d%%", key=slider_key,
                    )
                    driver_deltas[(drv, None)] = pct / 100.0

        if sep_mapped_drivers or sep_all_drivers:
            st.markdown("**🔵 Drivers riêng** _(mỗi đơn vị một thanh kéo)_")
            for drv in sep_mapped_drivers:
                st.markdown(f"**{drv}** · *theo mapping*")
                subs_for_drv = sorted(
                    df_kd_scoped[df_kd_scoped["key_drivers"] == drv]["ma_don_vi"]
                    .dropna().astype(str).unique().tolist()
                )
                cols = st.columns(3)
                for i, sub in enumerate(subs_for_drv):
                    with cols[i % 3]:
                        pct = st.slider(
                            sub, min_value=-50, max_value=100, value=0, step=1,
                            format="%d%%", key=f"p6_d__{drv}__{sub}",
                        )
                        driver_deltas[(drv, sub)] = pct / 100.0
            for drv in sep_all_drivers:
                st.markdown(
                    f"**{drv}** · *override — tất cả đơn vị đã chọn*"
                )
                cols = st.columns(3)
                for i, sub in enumerate(sel_units):
                    with cols[i % 3]:
                        pct = st.slider(
                            sub, min_value=-50, max_value=100, value=0, step=1,
                            format="%d%%", key=f"p6_d__{drv}__{sub}",
                        )
                        driver_deltas[(drv, sub)] = pct / 100.0
            if sep_all_drivers:
                st.caption(
                    "ℹ️ Thanh kéo cho đơn vị không có mapping driver trong "
                    "`df_key_drivers` sẽ không có tác dụng (engine chỉ shock "
                    "lines đã được mapping)."
                )

        with st.expander(
            "📑 Danh sách Chỉ tiêu CF & Drivers tác động", expanded=False
        ):
            _render_chi_tieu_drivers_view(df_report_scoped, df_kd_scoped)
    # ── End of driver controls expander ────────────────────────────────────

    # ── Engine ─────────────────────────────────────────────────────────────
    shocked = compute_shocked_cf(
        df_report_scoped, df_kd_scoped, edited, driver_deltas
    )
    if shocked.empty:
        st.info("Không có dữ liệu sau khi áp dụng bộ lọc.")
        return

    period_mode = st.session_state.get("p6_period_mode", "Quý") or "Quý"

    per_period = aggregate_per_period(shocked, period_mode)
    cum = cumulative_cash(per_period, cash_0)
    per_period_km = aggregate_per_period_per_km(shocked, period_mode)

    # ── Render results (visually BELOW driver controls) ────────────────────
    _render_scenario_summary(driver_deltas, edited)

    hr1, hr2 = st.columns([6, 2])
    with hr1:
        st.subheader("4️⃣ Kết quả")
    with hr2:
        st.segmented_control(
            "Hiển thị theo", ["Năm", "Quý"], default="Quý",
            key="p6_period_mode",
        )

    _render_compact_kpi_strip(per_period, cum, cash_0, per_period_km)

    floor = _render_floor_input_and_alert(cum)

    kc1, kc2 = st.columns([2, 5])
    with kc1:
        st.markdown("##### Phân rã theo Khoản mục")
    with kc2:
        sel_kms = st.multiselect(
            "Hiện Khoản mục", _KM_ORDER, default=_KM_ORDER,
            key="p6_km_selected", label_visibility="collapsed",
        )
    _render_km_chart(per_period_km, selected_kms=sel_kms)

    c_chart, c_cum = st.columns([1, 1])
    with c_chart:
        st.markdown("##### Dòng tiền theo kỳ — Gốc vs Sau shock")
        _render_period_chart(per_period)
    with c_cum:
        st.markdown("##### Lũy kế tiền")
        _render_cumulative_chart(cum, floor)

    with st.expander("📊 Xem bảng số liệu (Trước / Sau / Δ)", expanded=False):
        _render_comparison_pivot(shocked, period_mode)

    with st.expander("📋 Phân rã đóng góp Driver", expanded=False):
        deco = decomposition_table(
            df_report_scoped, df_kd_scoped, edited, driver_deltas
        )
        _render_decomposition(deco)

    with st.expander("🔍 Xem chi tiết per đơn vị / chi tiêu", expanded=False):
        detail = shocked.copy()
        detail["period"] = [
            _period_str(n, q, period_mode)
            for n, q in zip(detail["nam"], detail["quy"])
        ]
        detail["shock_pct"] = detail["shock_factor"] * 100.0
        st.dataframe(
            detail[[
                "ma_don_vi", "chi_tieu", "khoan_muc", "period",
                "baseline", "shock_pct", "shocked", "delta",
            ]],
            use_container_width=True, hide_index=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Render helpers
# ─────────────────────────────────────────────────────────────────────────────


def _render_chi_tieu_drivers_view(
    df_report_scoped: pd.DataFrame,
    df_kd_scoped: pd.DataFrame,
) -> None:
    """Reference table: each chỉ tiêu CF in scope + the drivers that touch it.

    Two views — toggle which one to show:
      • "Chỉ tiêu → Drivers" (default): one row per (khoản mục, chỉ tiêu)
      • "Driver → Chỉ tiêu": one row per driver, with affected chỉ tiêu
    """
    view = st.segmented_control(
        "Cách xem",
        ["Chỉ tiêu → Drivers", "Driver → Chỉ tiêu"],
        default="Chỉ tiêu → Drivers",
        key="p6_view_mode",
    ) or "Chỉ tiêu → Drivers"

    if df_kd_scoped.empty:
        kd = pd.DataFrame(columns=["ma_don_vi", "chi_tieu", "key_drivers"])
    else:
        kd = df_kd_scoped[df_kd_scoped["key_drivers"].notna()].copy()
        kd["key_drivers"] = kd["key_drivers"].astype(str).str.strip()
        kd = kd[(kd["key_drivers"] != "") & kd["ma_don_vi"].notna()]

    if view == "Chỉ tiêu → Drivers":
        ct = (
            df_report_scoped[df_report_scoped["khoan_muc"].isin(_KM_FILTER)]
            .groupby(["khoan_muc", "chi_tieu"], as_index=False)["ma_don_vi"]
            .nunique()
            .rename(columns={"ma_don_vi": "n_subs"})
        )
        if kd.empty:
            ct["drivers"] = "(không có)"
        else:
            drv_map = (
                kd.groupby("chi_tieu")["key_drivers"]
                .apply(lambda s: ", ".join(sorted(set(s))))
                .to_dict()
            )
            ct["drivers"] = ct["chi_tieu"].map(drv_map).fillna("(không có)")
        ct["_km_order"] = ct["khoan_muc"].map(
            {k: i for i, k in enumerate(_KM_ORDER)}
        ).fillna(99).astype(int)
        ct = (
            ct.sort_values(["_km_order", "chi_tieu"])
            .drop(columns="_km_order")
            .rename(columns={
                "khoan_muc": "Khoản mục",
                "chi_tieu": "Chỉ tiêu",
                "n_subs": "# Đơn vị có",
                "drivers": "Drivers tác động",
            })
        )
        st.caption(
            f"📋 **{len(ct)}** chỉ tiêu CF · "
            f"{(ct['Drivers tác động'] == '(không có)').sum()} chỉ tiêu chưa "
            "có driver mapping (sẽ giữ nguyên ở mức baseline)."
        )
        st.dataframe(ct, use_container_width=True, hide_index=True)
    else:
        # Driver → Chỉ tiêu
        if kd.empty:
            st.info("Không có driver nào được khai báo cho phạm vi này.")
            return
        # Restrict to chỉ tiêu actually present in df_report_scoped
        scope_ct = set(
            df_report_scoped[df_report_scoped["khoan_muc"].isin(_KM_FILTER)]
            ["chi_tieu"].dropna().astype(str).unique()
        )
        kd_in_scope = kd[kd["chi_tieu"].astype(str).isin(scope_ct)]
        rows = (
            kd_in_scope.groupby("key_drivers")
            .agg(
                n_subs=("ma_don_vi", "nunique"),
                n_chi_tieu=("chi_tieu", "nunique"),
                chi_tieu_list=("chi_tieu", lambda s: ", ".join(sorted(set(s)))),
            )
            .reset_index()
            .rename(columns={
                "key_drivers": "Driver",
                "n_subs": "# Đơn vị",
                "n_chi_tieu": "# Chỉ tiêu",
                "chi_tieu_list": "Chỉ tiêu tác động",
            })
            .sort_values("# Chỉ tiêu", ascending=False)
        )
        st.caption(
            f"⚙️ **{len(rows)}** driver tác động lên ít nhất 1 chỉ tiêu trong phạm vi."
        )
        st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_baseline_only(df_report_scoped: pd.DataFrame, cash_0: float) -> None:
    base = df_report_scoped[df_report_scoped["khoan_muc"].isin(_KM_FILTER)]
    total = float(base["so_tien_tong"].sum())
    st.metric("Tổng CF gốc (chưa shock)", fmt_money_short(total))
    st.caption(f"Số dư đầu kỳ = {fmt_money_short(cash_0)} triệu VNĐ")


def _render_kpi_row(
    per_period: pd.DataFrame, cum: pd.DataFrame, cash_0: float
) -> None:
    sum_baseline = float(per_period["baseline"].sum())
    sum_shocked = float(per_period["shocked"].sum())
    delta_total = sum_shocked - sum_baseline
    min_baseline = float(cum["baseline_cum"].min()) if not cum.empty else cash_0
    min_shocked = float(cum["shocked_cum"].min()) if not cum.empty else cash_0
    delta_min = min_shocked - min_baseline

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Tổng CF gốc", fmt_money_short(sum_baseline))
    k2.metric("Tổng CF sau shock", fmt_money_short(sum_shocked))
    pct = (delta_total / sum_baseline * 100.0) if sum_baseline else 0.0
    k3.metric(
        "Δ Tổng CF",
        fmt_money_short(delta_total),
        delta=f"{pct:+.1f}%" if sum_baseline else None,
    )
    k4.metric("Δ Min cash trong kỳ", fmt_money_short(delta_min))


def _render_scenario_summary(
    driver_deltas: dict[tuple[str, str | None], float],
    driver_specs: pd.DataFrame,
) -> None:
    """One-line banner summarizing active shocks + non-default ε/lag overrides.

    Renders an info banner when no shocks are applied (helps first-time users
    locate the driver controls) and a warning-tinted banner when shocks are
    active — terms are joined with ' · ' so the line stays scannable.
    """
    parts: list[str] = []
    for (drv, sub), delta in driver_deltas.items():
        if abs(delta) < 1e-6:
            continue
        pct = delta * 100.0
        scope = "" if sub is None else f" ({sub})"
        parts.append(f"{drv}{scope} {pct:+.0f}%")
    if not driver_specs.empty:
        for _, spec in driver_specs.iterrows():
            try:
                eps = float(spec.get("elasticity") or 1.0)
            except (TypeError, ValueError):
                eps = 1.0
            try:
                lag = int(spec.get("lag") or 0)
            except (TypeError, ValueError):
                lag = 0
            drv = spec["driver"]
            if abs(eps - 1.0) > 1e-3:
                parts.append(f"{drv} ε={eps:.1f}")
            if lag != 0:
                parts.append(f"{drv} lag={lag:+d}q")
    if not parts:
        st.markdown(
            "<div style='background:#eef2f5;border-left:4px solid #95a5a6;"
            "padding:8px 12px;border-radius:4px;font-size:13px;color:#566573;"
            "margin-bottom:8px'>"
            "💡 Chưa áp dụng shock. Mở <b>🎚️ Điều chỉnh kịch bản</b> ở trên "
            "để mô phỏng.</div>",
            unsafe_allow_html=True,
        )
        return
    badge_text = "🔥 " + " · ".join(parts)
    st.markdown(
        f"<div style='background:#fff3cd;border-left:4px solid #f0ad4e;"
        f"padding:8px 12px;border-radius:4px;font-size:13px;color:#7d6608;"
        f"margin-bottom:8px'>{badge_text}</div>",
        unsafe_allow_html=True,
    )


def _render_compact_kpi_strip(
    per_period: pd.DataFrame,
    cum: pd.DataFrame,
    cash_0: float,
    per_period_km: pd.DataFrame,
) -> None:
    """One-row HTML strip with all 7 metrics (4 main + 3 KM Δ).

    Replaces the old `_render_kpi_row` (st.metric × 4) +
    `_render_km_kpi` (st.metric × 3) which together consumed two rows.
    """
    sum_baseline = float(per_period["baseline"].sum())
    sum_shocked = float(per_period["shocked"].sum())
    delta_total = sum_shocked - sum_baseline
    pct_total = (delta_total / sum_baseline * 100.0) if sum_baseline else 0.0
    min_baseline = (
        float(cum["baseline_cum"].min()) if not cum.empty else cash_0
    )
    min_shocked = (
        float(cum["shocked_cum"].min()) if not cum.empty else cash_0
    )
    delta_min = min_shocked - min_baseline
    pct_min = (delta_min / abs(min_baseline) * 100.0) if min_baseline else 0.0

    if per_period_km.empty:
        km_totals = pd.DataFrame()
    else:
        km_totals = per_period_km.groupby("khoan_muc")[
            ["baseline", "shocked", "delta"]
        ].sum()

    def _cell(label: str, value: float, pct: float | None = None,
              sign: bool = False) -> str:
        val_color = ""
        if sign and value != 0:
            val_color = (
                "color:#1e8449;" if value > 0 else "color:#c0392b;"
            )
        val_str = fmt_money_short(value) if not pd.isna(value) else "—"
        pct_html = ""
        if pct is not None:
            if pct > 0:
                pct_color, arrow = "#1e8449", "↑"
            elif pct < 0:
                pct_color, arrow = "#c0392b", "↓"
            else:
                pct_color, arrow = "#888", "·"
            pct_html = (
                f'<span class="kpi-pct" style="color:{pct_color};">'
                f'{arrow} {pct:+.1f}%</span>'
            )
        return (
            f'<div class="kpi-cell">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-val" style="{val_color}">{val_str}</div>'
            f'{pct_html}'
            f'</div>'
        )

    cells: list[str] = [
        _cell("Tổng CF gốc", sum_baseline),
        _cell("Sau shock", sum_shocked),
        _cell("Δ Tổng CF", delta_total, pct=pct_total, sign=True),
        _cell("Δ Min cash", delta_min, pct=pct_min, sign=True),
    ]
    for km in _KM_ORDER:
        if km in km_totals.index:
            d = float(km_totals.loc[km, "delta"])
            b = float(km_totals.loc[km, "baseline"])
            kpct = (d / b * 100.0) if b else 0.0
            cells.append(_cell(f"Δ {km}", d, pct=kpct, sign=True))
        else:
            cells.append(_cell(f"Δ {km}", 0.0))

    css = """
    <style>
    .kpi-strip { display:flex; gap:6px; margin:4px 0 12px 0;
                 font-family:'Inter','Segoe UI',Roboto,sans-serif; }
    .kpi-cell { flex:1; padding:6px 10px; border:1px solid #e3e6ea;
                border-radius:6px; background:#fafbfc; min-width:0; }
    .kpi-label { font-size:10px; color:#6c757d; text-transform:uppercase;
                 letter-spacing:0.4px; white-space:nowrap;
                 overflow:hidden; text-overflow:ellipsis; }
    .kpi-val { font-size:17px; font-weight:700; color:#2c3e50;
               margin-top:2px; line-height:1.15; }
    .kpi-pct { font-size:11px; font-weight:600; }
    </style>
    """
    st.markdown(
        css + f'<div class="kpi-strip">{"".join(cells)}</div>',
        unsafe_allow_html=True,
    )


def _render_comparison_pivot(shocked: pd.DataFrame, period_mode: str) -> None:
    oc1, oc2, oc3 = st.columns([2, 2, 5])
    with oc1:
        unit_label = st.segmented_control(
            "Đơn vị", ["Triệu", "Tỷ"],
            default="Triệu", key="p6_pv_unit",
        ) or "Triệu"
    with oc2:
        show_delta = st.checkbox(
            "Hiển thị Δ", value=True, key="p6_pv_show_delta",
            help="Cộng thêm dòng Δ (Sau − Trước) vào mỗi ô.",
        )
    unit_divisor = 1.0 if unit_label == "Triệu" else 1000.0
    fmt_str = "{:+,.0f}" if unit_label == "Triệu" else "{:+,.1f}"

    df = shocked.copy()
    df["_period"] = [
        _period_str(n, q, period_mode)
        for n, q in zip(df["nam"], df["quy"])
    ]

    detail_cts = sorted(df["chi_tieu"].dropna().astype(str).unique().tolist())
    with oc3:
        shown_cts = st.multiselect(
            "Hiển thị Chỉ tiêu (Net & Tổng cộng giữ nguyên)",
            detail_cts, default=detail_cts,
            key="p6_pv_show_ct",
            help="Bỏ tick để ẩn các chỉ tiêu chi tiết. Net và Tổng cộng vẫn "
                 "tính trên TẤT CẢ chỉ tiêu.",
        )

    period_cols = sorted(df["_period"].unique().tolist(), key=_period_sort_key)

    pivot_baseline = df.pivot_table(
        index=["ma_don_vi", "khoan_muc", "chi_tieu"],
        columns="_period", values="baseline", aggfunc="sum", fill_value=0,
    ).reindex(columns=period_cols, fill_value=0)
    pivot_shocked = df.pivot_table(
        index=["ma_don_vi", "khoan_muc", "chi_tieu"],
        columns="_period", values="shocked", aggfunc="sum", fill_value=0,
    ).reindex(columns=period_cols, fill_value=0)
    pivot_delta = pivot_shocked - pivot_baseline

    flat_b = pivot_baseline.reset_index()
    flat_s = pivot_shocked.reset_index()
    flat_d = pivot_delta.reset_index()

    flat_b["_km_order"] = flat_b["khoan_muc"].map(
        {k: i for i, k in enumerate(_KM_ORDER)}
    ).fillna(99).astype(int)
    flat_b = flat_b.sort_values(["ma_don_vi", "_km_order", "chi_tieu"]).drop(
        columns="_km_order"
    )

    units = list(dict.fromkeys(flat_b["ma_don_vi"].tolist()))

    def _row_for(unit: str, km: str, ct: str, source: pd.DataFrame) -> list[float]:
        row = source[
            (source["ma_don_vi"] == unit)
            & (source["khoan_muc"] == km)
            & (source["chi_tieu"] == ct)
        ]
        if row.empty:
            return [0.0] * len(period_cols)
        return [float(row[p].values[0]) for p in period_cols]

    rows: list[dict] = []
    for unit in units:
        unit_subset = flat_b[flat_b["ma_don_vi"] == unit]
        for _, r in unit_subset.iterrows():
            ct = str(r["chi_tieu"])
            if ct not in shown_cts:
                continue
            km = str(r["khoan_muc"])
            rows.append({
                "unit": str(unit), "km": km, "ct": ct,
                "baseline": [float(r[p]) for p in period_cols],
                "shocked": _row_for(str(unit), km, ct, flat_s),
                "delta": _row_for(str(unit), km, ct, flat_d),
                "is_net": False,
            })
        # Net per unit (across ALL chi_tieu — like p3_pivot)
        all_b = flat_b[flat_b["ma_don_vi"] == unit]
        all_s = flat_s[flat_s["ma_don_vi"] == unit]
        all_d = flat_d[flat_d["ma_don_vi"] == unit]
        rows.append({
            "unit": str(unit), "km": "", "ct": "Net",
            "baseline": [float(all_b[p].sum()) for p in period_cols],
            "shocked": [float(all_s[p].sum()) for p in period_cols],
            "delta": [float(all_d[p].sum()) for p in period_cols],
            "is_net": True,
        })

    if not rows:
        st.info("Không có dữ liệu hiển thị.")
        return

    # ── Heatmap tint scale: max |Δ| across detail rows (Net excluded so it
    # doesn't dominate). Used by _cell_bg to compute per-cell background.
    max_abs_delta = 0.0
    for r in rows:
        if r["is_net"]:
            continue
        for d in r["delta"]:
            ad = abs(float(d))
            if ad > max_abs_delta:
                max_abs_delta = ad

    def _cell_bg(d: float) -> str:
        if max_abs_delta <= 0 or d == 0:
            return ""
        intensity = min(1.0, abs(d) / max_abs_delta) * 0.35
        if d < 0:
            return f"background:rgba(192,57,43,{intensity:.3f})"
        return f"background:rgba(30,132,73,{intensity:.3f})"

    # Grand total (Σ Net)
    net_rows = [r for r in rows if r["is_net"]]
    if net_rows:
        n = len(period_cols)
        rows.append({
            "unit": "TỔNG CỘNG", "km": "", "ct": "Net",
            "baseline": [sum(r["baseline"][i] for r in net_rows) for i in range(n)],
            "shocked": [sum(r["shocked"][i] for r in net_rows) for i in range(n)],
            "delta": [sum(r["delta"][i] for r in net_rows) for i in range(n)],
            "is_net": True, "is_grand": True,
        })

    unit_counts: dict[str, int] = {}
    for r in rows:
        if r.get("is_grand"):
            continue
        unit_counts[r["unit"]] = unit_counts.get(r["unit"], 0) + 1
    km_counts: dict[tuple[str, str], int] = {}
    for r in rows:
        if r.get("is_grand") or r["is_net"]:
            continue
        km_counts[(r["unit"], r["km"])] = km_counts.get((r["unit"], r["km"]), 0) + 1

    unit_short = "triệu" if unit_label == "Triệu" else "tỷ"
    header_cells = [
        '<th class="hdr">Đơn vị</th>',
        '<th class="hdr">Khoản mục</th>',
        f'<th class="hdr">Chỉ tiêu ({unit_short} VNĐ)</th>',
    ]
    header_cells += [f'<th class="hdr">{c}</th>' for c in period_cols]
    header_html = "<tr>" + "".join(header_cells) + "</tr>"

    def _format_cell(b: float, s: float, d: float) -> tuple[str, str]:
        sign = "neg" if d < 0 else ("pos" if d > 0 else "")
        parts = [
            f'<span class="lbl">Trước</span> {fmt_str.format(b / unit_divisor).lstrip("+")}',
            f'<span class="lbl">Sau</span> {fmt_str.format(s / unit_divisor).lstrip("+")}',
        ]
        if show_delta:
            parts.append(
                f'<span class="lbl-d">Δ</span> {fmt_str.format(d / unit_divisor)}'
            )
        return "<br>".join(parts), sign

    body_rows: list[str] = []
    seen_units: set[str] = set()
    seen_unit_km: set[tuple[str, str]] = set()
    n_period = len(period_cols)

    for r in rows:
        unit = r["unit"]
        is_net = r["is_net"]
        is_grand = r.get("is_grand", False)
        tr_class = "grand-row" if is_grand else ("net-row" if is_net else "")
        cells: list[str] = []

        if is_grand:
            cells.append(
                '<td class="grand-cell" colspan="3">'
                "<strong>TỔNG CỘNG (Σ Net)</strong></td>"
            )
            for i in range(n_period):
                txt, sign = _format_cell(r["baseline"][i], r["shocked"][i], r["delta"][i])
                cls = ["num", "grand-cell"]
                if sign:
                    cls.append(sign)
                cells.append(f'<td class="{" ".join(cls)}">{txt}</td>')
            body_rows.append(f'<tr class="{tr_class}">' + "".join(cells) + "</tr>")
            continue

        if unit not in seen_units:
            seen_units.add(unit)
            cells.append(
                f'<td rowspan="{unit_counts[unit]}" class="unit-cell">{unit}</td>'
            )

        km = r.get("km", "")
        if is_net:
            cells.append(
                '<td class="ct-cell" colspan="2"><strong>Net</strong></td>'
            )
        else:
            km_key = (unit, km)
            if km_key not in seen_unit_km:
                seen_unit_km.add(km_key)
                cells.append(
                    f'<td rowspan="{km_counts[km_key]}" class="km-cell">{km}</td>'
                )
            cells.append(f'<td class="ct-cell">{r["ct"]}</td>')

        for i in range(n_period):
            txt, sign = _format_cell(r["baseline"][i], r["shocked"][i], r["delta"][i])
            cls = ["num"]
            if sign:
                cls.append(sign)
            # Heatmap tint only for detail rows (Net + Grand keep their bg)
            style = (
                f' style="{_cell_bg(r["delta"][i])}"'
                if not r["is_net"] else ""
            )
            cells.append(f'<td class="{" ".join(cls)}"{style}>{txt}</td>')
        body_rows.append(f'<tr class="{tr_class}">' + "".join(cells) + "</tr>")

    css = """
    <style>
    .p6-pivot { border-collapse: collapse; width: 100%; font-size: 12px;
                font-family: 'Inter', 'Segoe UI', Roboto, sans-serif;
                line-height: 1.25; }
    .p6-pivot th, .p6-pivot td { border: 1px solid #d9dfe6; padding: 4px 8px; }
    .p6-pivot th.hdr { background: #f0f4f8; font-weight: 700; text-align: center; }
    .p6-pivot td.unit-cell { background: #fdecea; font-weight: 700;
                             text-align: center; vertical-align: middle;
                             font-size: 13px; }
    .p6-pivot td.km-cell { background: #eef5fb; font-weight: 700;
                           text-align: center; vertical-align: middle;
                           color: #2c3e50; }
    .p6-pivot td.ct-cell { text-align: left; font-weight: 600; }
    .p6-pivot td.num { text-align: right; font-variant-numeric: tabular-nums; }
    .p6-pivot tr.net-row td { background: #e3edf7; font-weight: 700; }
    .p6-pivot tr.grand-row td.grand-cell {
        background: #2c3e50; color: white; font-weight: 700; font-size: 13px;
        text-align: center; padding: 5px 8px;
    }
    .p6-pivot tr.grand-row td.grand-cell.num { text-align: right; }
    .p6-pivot .neg { color: #c0392b; font-weight: 600; }
    .p6-pivot .pos { color: #1e8449; font-weight: 600; }
    .p6-pivot tr.grand-row td.grand-cell.neg { color: #ff7d6e; }
    .p6-pivot tr.grand-row td.grand-cell.pos { color: #88e0a5; }
    .p6-pivot .lbl, .p6-pivot .lbl-d { display: inline-block; min-width: 36px;
                                       color: #888; font-size: 10px;
                                       text-align: left; margin-right: 4px; }
    .p6-pivot .lbl-d { color: #2c3e50; font-weight: 700; min-width: 14px; }
    </style>
    """

    pv_height = 480
    html = (
        css
        + f'<div style="overflow-x:auto;max-height:{pv_height}px;overflow-y:auto;">'
        + '<table class="p6-pivot">'
        + "<thead>" + header_html + "</thead>"
        + "<tbody>" + "".join(body_rows) + "</tbody>"
        + "</table></div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def _render_km_kpi(per_period_km: pd.DataFrame) -> None:
    """3 KPI cards (CFO / CFI / CFF), each showing Δ + % vs baseline."""
    if per_period_km.empty:
        return
    totals = per_period_km.groupby("khoan_muc")[["baseline", "shocked", "delta"]].sum()
    cols = st.columns(3)
    for i, km in enumerate(_KM_ORDER):
        with cols[i]:
            if km in totals.index:
                b = float(totals.loc[km, "baseline"])
                d = float(totals.loc[km, "delta"])
                pct = (d / b * 100.0) if b else 0.0
                st.metric(
                    f"{km} — Δ",
                    fmt_money_short(d),
                    delta=f"{pct:+.1f}%" if b else None,
                )
            else:
                st.metric(f"{km} — Δ", "—")


def _render_km_chart(
    per_period_km: pd.DataFrame, selected_kms: list[str] | None = None
) -> None:
    """N-panel chart per khoản mục: grouped bars (Gốc vs Sau shock) +
    cumulative lines (Lũy kế Gốc vs Lũy kế Sau) on the same y-axis."""
    if per_period_km.empty:
        return
    if selected_kms is None:
        selected_kms = _KM_ORDER
    selected_kms = [km for km in _KM_ORDER if km in selected_kms]
    if not selected_kms:
        st.info("Tick ít nhất một Khoản mục để hiển thị.")
        return
    height = 380
    n_cols = len(selected_kms)
    fig = make_subplots(
        rows=1, cols=n_cols, subplot_titles=selected_kms,
        shared_yaxes=False, horizontal_spacing=0.06,
    )
    for i, km in enumerate(selected_kms, start=1):
        df = per_period_km[per_period_km["khoan_muc"] == km]
        if df.empty:
            continue
        km_color = KHOAN_MUC_COLORS.get(km, "#4C72B0")
        baseline_cum = df["baseline"].cumsum()
        shocked_cum = df["shocked"].cumsum()

        fig.add_trace(
            go.Bar(
                name="Gốc", x=df["period"], y=df["baseline"],
                marker_color="#9aa0a6",
                text=[fmt_money_short(v) for v in df["baseline"]],
                textposition="outside", textangle=-30,
                textfont=dict(size=9, color="#5f6368"),
                cliponaxis=False,
                showlegend=(i == 1), legendgroup="goc",
                hovertemplate="<b>%{x} · " + km + "</b><br>"
                              "Gốc: %{y:,.0f} triệu<extra></extra>",
            ),
            row=1, col=i,
        )
        fig.add_trace(
            go.Bar(
                name="Sau shock", x=df["period"], y=df["shocked"],
                marker_color=km_color,
                text=[fmt_money_short(v) for v in df["shocked"]],
                textposition="outside", textangle=-30,
                textfont=dict(size=9, color=km_color),
                cliponaxis=False,
                showlegend=(i == 1), legendgroup="shock",
                hovertemplate="<b>%{x} · " + km + "</b><br>"
                              "Sau shock: %{y:,.0f} triệu<extra></extra>",
            ),
            row=1, col=i,
        )
        fig.add_trace(
            go.Scatter(
                name="Lũy kế Gốc", x=df["period"], y=baseline_cum,
                mode="lines+markers+text",
                line=dict(color="#5f6368", width=2, dash="dash"),
                marker=dict(size=6, symbol="circle-open"),
                text=[fmt_money_short(v) for v in baseline_cum],
                textposition="top center",
                textfont=dict(size=9, color="#5f6368"),
                cliponaxis=False,
                showlegend=(i == 1), legendgroup="cum_goc",
                hovertemplate="<b>%{x} · " + km + "</b><br>"
                              "Lũy kế Gốc: %{y:,.0f} triệu<extra></extra>",
            ),
            row=1, col=i,
        )
        fig.add_trace(
            go.Scatter(
                name="Lũy kế Sau shock", x=df["period"], y=shocked_cum,
                mode="lines+markers+text",
                line=dict(color=km_color, width=2.5),
                marker=dict(size=7, symbol="diamond"),
                text=[fmt_money_short(v) for v in shocked_cum],
                textposition="bottom center",
                textfont=dict(size=9, color=km_color),
                cliponaxis=False,
                showlegend=(i == 1), legendgroup="cum_sau",
                hovertemplate="<b>%{x} · " + km + "</b><br>"
                              "Lũy kế Sau: %{y:,.0f} triệu<extra></extra>",
            ),
            row=1, col=i,
        )
    fig.update_layout(
        barmode="group", height=height,
        margin=dict(l=0, r=0, t=60, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.08,
                    xanchor="left", x=0),
        uniformtext=dict(mode="show", minsize=8),
    )
    fig.update_yaxes(title_text="triệu VNĐ", col=1)
    st.plotly_chart(fig, use_container_width=True, key="p6_km_chart")


def _render_period_chart(per_period: pd.DataFrame) -> None:
    if per_period.empty:
        st.info("Không có dữ liệu kỳ.")
        return
    height = 420
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Gốc", x=per_period["period"], y=per_period["baseline"],
        marker_color="#9aa0a6",
        text=[fmt_money_short(v) for v in per_period["baseline"]],
        textposition="outside", textangle=-30,
        textfont=dict(size=10, color="#5f6368"),
        cliponaxis=False,
        hovertemplate="<b>%{x}</b><br>Gốc: %{y:,.0f} triệu<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Sau shock", x=per_period["period"], y=per_period["shocked"],
        marker_color="#4C72B0",
        text=[fmt_money_short(v) for v in per_period["shocked"]],
        textposition="outside", textangle=-30,
        textfont=dict(size=10, color="#1f3b66"),
        cliponaxis=False,
        hovertemplate="<b>%{x}</b><br>Sau shock: %{y:,.0f} triệu<extra></extra>",
    ))
    fig.update_layout(
        barmode="group", height=height,
        margin=dict(l=0, r=0, t=50, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        yaxis_title="Dòng tiền (triệu VNĐ)",
        uniformtext=dict(mode="show", minsize=9),
    )
    st.plotly_chart(fig, use_container_width=True, key="p6_period_chart")


def _render_floor_input_and_alert(cum: pd.DataFrame) -> float:
    """Floor input + breach banner. Returns the floor value for chart use."""
    if "p6_cash_floor" not in st.session_state:
        st.session_state["p6_cash_floor"] = 0.0
    fc1, fc2 = st.columns([1, 4])
    with fc1:
        floor = st.number_input(
            "Sàn tiền (triệu, 0 = ẩn)",
            step=1000.0, format="%.0f", key="p6_cash_floor",
        )
    if floor != 0 and not cum.empty:
        breaches = cum[cum["shocked_cum"] < floor]
        with fc2:
            if breaches.empty:
                st.success("✅ Lũy kế tiền không vỡ sàn trong kỳ mô phỏng.")
            else:
                first = breaches.iloc[0]
                st.error(
                    f"⚠️ Vỡ sàn tiền tại **{first['period']}** · "
                    f"Lũy kế = {fmt_money_short(float(first['shocked_cum']))} · "
                    f"Sàn = {fmt_money_short(float(floor))} · "
                    f"({len(breaches)} kỳ vi phạm)"
                )
    return float(floor)


def _render_cumulative_chart(cum: pd.DataFrame, floor: float = 0.0) -> None:
    if cum.empty:
        st.info("Không có dữ liệu lũy kế.")
        return
    height = 420
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=cum["period"], y=cum["baseline_cum"], name="Gốc",
        mode="lines+markers+text", line=dict(color="#9aa0a6", width=2.5),
        text=[fmt_money_short(v) for v in cum["baseline_cum"]],
        textposition="top center",
        textfont=dict(size=10, color="#5f6368"),
        cliponaxis=False,
        hovertemplate="<b>%{x}</b><br>Lũy kế (gốc): %{y:,.0f} triệu<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=cum["period"], y=cum["shocked_cum"], name="Sau shock",
        mode="lines+markers+text", line=dict(color="#4C72B0", width=2.5),
        text=[fmt_money_short(v) for v in cum["shocked_cum"]],
        textposition="bottom center",
        textfont=dict(size=10, color="#1f3b66"),
        cliponaxis=False,
        hovertemplate="<b>%{x}</b><br>Lũy kế (shock): %{y:,.0f} triệu<extra></extra>",
    ))
    if floor != 0:
        fig.add_hline(
            y=floor, line_dash="dot", line_color="#c0392b",
            annotation_text="Sàn tiền", annotation_position="top right",
        )
        breaches = cum[cum["shocked_cum"] < floor]
        if not breaches.empty:
            fig.add_trace(go.Scatter(
                x=breaches["period"], y=breaches["shocked_cum"],
                name="Vỡ sàn", mode="markers",
                marker=dict(size=12, color="#c0392b",
                            line=dict(width=1, color="#7b1f15")),
                hovertemplate="<b>%{x}</b><br>Vỡ sàn: %{y:,.0f} triệu"
                              "<extra></extra>",
            ))
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=30, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        yaxis_title="Số dư tích lũy (triệu VNĐ)",
    )
    st.plotly_chart(fig, use_container_width=True, key="p6_cum_chart")


def _render_decomposition(deco: pd.DataFrame) -> None:
    if deco.empty:
        st.caption("Không có driver nào đang áp dụng.")
        return
    st.caption(
        "ℹ️ Bảng này chỉ phân rã đóng góp từ **% slider**. "
        "Hiệu ứng **lag** (dịch dòng tiền) đã tính trong KPI Δ Tổng CF "
        "nhưng không tách riêng theo driver ở đây."
    )

    # Display values in TỶ (÷ 1,000) so the numbers fit and read cleanly.
    deco_disp = deco.copy()
    deco_disp["baseline_sum"] = deco_disp["baseline_sum"] / 1000.0
    deco_disp["contribution"] = deco_disp["contribution"] / 1000.0
    deco_disp = deco_disp.rename(columns={
        "driver": "Driver",
        "mode": "Loại",
        "delta_pct_avg": "Δ slider (%)",
        "lag": "Lag (quý)",
        "elasticity": "Elasticity",
        "baseline_sum": "Σ baseline (tỷ)",
        "contribution": "Đóng góp Δ (tỷ)",
        "pct_of_total": "% tổng Δ",
    })
    contrib_col = "Đóng góp Δ (tỷ)"
    baseline_col = "Σ baseline (tỷ)"
    pct_col = "% tổng Δ"
    pct_slider_col = "Δ slider (%)"

    # Append Total row. Aggregables = sum; per-driver attrs (Δ slider, Lag, Elasticity, Loại) left blank.
    total_row = pd.DataFrame([{
        "Driver": "Σ Tổng",
        "Loại": "",
        pct_slider_col: pd.NA,
        "Lag (quý)": pd.NA,
        "Elasticity": pd.NA,
        baseline_col: float(deco_disp[baseline_col].sum()),
        contrib_col: float(deco_disp[contrib_col].sum()),
        pct_col: 100.0,
    }])
    deco_disp = pd.concat([deco_disp, total_row], ignore_index=True)
    drv_idx = deco_disp.index[:-1]

    def _sign_color(v):
        if v is None or pd.isna(v):
            return ""
        try:
            f = float(v)
        except (TypeError, ValueError):
            return ""
        if f < 0:
            return "color: #c0392b; font-weight: 600"
        if f > 0:
            return "color: #1e8449; font-weight: 600"
        return "color: #95a5a6"

    def _mode_color(v):
        s = str(v)
        if s == "Common":
            return "color: #1f618d; font-weight: 600"
        if s == "Separate":
            return "color: #b9770e; font-weight: 600"
        if s == "Override":
            return "color: #6c3483; font-weight: 600"
        return ""

    def _fmt_int_signed(v):
        if pd.isna(v):
            return "—"
        return f"{int(v):+d}"

    def _fmt_elast(v):
        if pd.isna(v):
            return "—"
        return f"{float(v):.2f}"

    def _fmt_pct_signed(v):
        if pd.isna(v):
            return "—"
        return f"{float(v):+.1f}%"

    def _fmt_money_signed(v):
        if pd.isna(v):
            return "—"
        return f"{float(v):+,.1f}"

    def _total_row_style(row):
        if row["Driver"] == "Σ Tổng":
            return ["background-color: #2c3e50; color: white; font-weight: 700"] * len(row)
        return [""] * len(row)

    styled = (
        deco_disp.style
        .format({
            pct_slider_col: _fmt_pct_signed,
            "Lag (quý)": _fmt_int_signed,
            "Elasticity": _fmt_elast,
            baseline_col: _fmt_money_signed,
            contrib_col: _fmt_money_signed,
            pct_col: _fmt_pct_signed,
        })
        .map(_sign_color,
             subset=pd.IndexSlice[drv_idx, [contrib_col, pct_col, baseline_col, pct_slider_col]])
        .map(_mode_color, subset=pd.IndexSlice[drv_idx, ["Loại"]])
    )

    # Diverging data bar on driver rows only — Total row excluded so its sum doesn't crush the scale.
    max_abs = float(deco_disp.loc[drv_idx, contrib_col].abs().max() or 1.0)
    if max_abs > 0:
        styled = styled.bar(
            subset=pd.IndexSlice[drv_idx, contrib_col],
            align="zero",
            color=["#f1948a", "#7dcea0"],
            vmin=-max_abs, vmax=max_abs,
        )

    # Total row style applied LAST so its dark background overrides per-cell colors above.
    styled = styled.apply(_total_row_style, axis=1)

    st.dataframe(styled, use_container_width=True, hide_index=True)
