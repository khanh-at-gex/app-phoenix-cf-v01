"""P3 Tab — Bảng pivot dòng tiền.

Multi-index table:
- Rows: (Đơn vị, Loại giao dịch) + 1 dòng "Net" per đơn vị
- Cols: period (Năm hoặc Quý)
- Values: sum(so_tien_tong)

Filters identical với Heatmap tab.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.ui import chart_height_slider


def render(
    *,
    base: pd.DataFrame,
    ordered_labels: list[str],
    label_to_unit: dict[str, str],
) -> None:
    """Render Pivot tab in-place. Đơn vị filter dùng folder-mapped labels giống P4."""
    st.caption("Bảng pivot: rows = Đơn vị × Loại giao dịch (kèm Net), cols = period")

    # ── Display options ────────────────────────────────────────────────────
    oc1, oc2, oc3, oc4 = st.columns([1, 1, 2, 2])
    with oc1:
        show_net = st.checkbox(
            "Hiển thị Net", value=True, key="p3_pv_show_net",
            help="Tổng (= Net) mỗi đơn vị theo period",
        )
    with oc2:
        show_format = st.checkbox(
            "Conditional format", value=True, key="p3_pv_show_format",
            help="Tô màu theo dấu (xanh dương / đỏ âm)",
        )
    with oc3:
        unit_label = st.segmented_control(
            "Đơn vị", ["Triệu", "Tỷ"],
            default="Triệu", key="p3_pv_unit",
            help="Triệu = data gốc · Tỷ = data ÷ 1,000",
        ) or "Triệu"
    with oc4:
        extra_breakdowns = st.multiselect(
            "Phân rã thêm theo",
            ["Đối tác", "Ổn định", "Nội/Ngoại"],
            default=[], key="p3_pv_extras",
            help="Thêm sub-row breakdown — mỗi (Đơn vị × Loại giao dịch) "
                 "chia thành nhiều sub-rows theo các trường được chọn",
        )
    show_dt = "Đối tác" in extra_breakdowns
    show_od = "Ổn định" in extra_breakdowns
    show_nn = "Nội/Ngoại" in extra_breakdowns
    unit_divisor = 1.0 if unit_label == "Triệu" else 1000.0
    fmt_str = "{:,.0f}" if unit_label == "Triệu" else "{:,.1f}"

    # ── Filter row ──────────────────────────────────────────────────────────
    fc1, fc2, fc3, fc4, fc5, fc6 = st.columns([3, 2, 2, 2, 2, 3])
    # Đơn vị filter dùng folder-mapped labels (giống P4) — restrict tới
    # units có trong base hiện tại
    units_in_base = set(base["ma_don_vi"].dropna().astype(str).unique())
    visible_unit_labels = [
        lb for lb in ordered_labels if label_to_unit.get(lb) in units_in_base
    ]
    with fc1:
        sel_unit_labels = st.multiselect(
            "Đơn vị", visible_unit_labels, key="p3_pv_units",
        )
        sel_units = [label_to_unit[lb] for lb in sel_unit_labels]
    with fc2:
        period_mode = st.segmented_control(
            "Show theo", ["Năm", "Quý"],
            default="Năm", key="p3_pv_period",
        ) or "Năm"
    with fc3:
        on_dinh = st.segmented_control(
            "Phân loại ổn định", ["Tất cả", "Ổn định", "Không ổn định"],
            default="Tất cả", key="p3_pv_on_dinh",
        ) or "Tất cả"
    with fc4:
        noi_ngoai = st.segmented_control(
            "Phân loại nội/ngoại", ["Tất cả", "Bên trong", "Bên ngoài"],
            default="Tất cả", key="p3_pv_noi_ngoai",
        ) or "Tất cả"
    with fc5:
        km = st.segmented_control(
            "Khoản mục", ["Tất cả", "CFO", "CFI", "CFF"],
            default="Tất cả", key="p3_pv_km",
        ) or "Tất cả"

    if km != "Tất cả":
        ct_scope = base[base["khoan_muc"] == km]
    else:
        ct_scope = base[base["khoan_muc"].isin(["CFO", "CFI", "CFF"])]
    ct_opts = sorted(ct_scope["chi_tieu"].dropna().unique().tolist())

    with fc6:
        sel_chi_tieu = st.multiselect(
            "Loại giao dịch", ct_opts, key="p3_pv_chi_tieu",
        )

    # ── Apply filters ──────────────────────────────────────────────────────
    if period_mode == "Quý":
        df = base[base["quy"].notna()].copy()
    else:
        df = base.copy()
    if on_dinh != "Tất cả":
        df = df[df["phan_loai_on_dinh_khong_on_dinh"] == on_dinh]
    if noi_ngoai != "Tất cả":
        df = df[df["phan_loai_ben_trong_ben_ngoai"] == noi_ngoai]
    if km != "Tất cả":
        df = df[df["khoan_muc"] == km]
    else:
        df = df[df["khoan_muc"].isin(["CFO", "CFI", "CFF"])]
    if sel_units:
        df = df[df["ma_don_vi"].isin(sel_units)]
    if sel_chi_tieu:
        df = df[df["chi_tieu"].isin(sel_chi_tieu)]

    if df.empty:
        st.info("Không có dữ liệu với bộ lọc hiện tại.")
        return

    # ── Build period column ────────────────────────────────────────────────
    if period_mode == "Quý":
        df["_period"] = (
            df["nam"].astype(str)
            + "-Q" + df["quy"].astype(int).astype(str)
        )
    else:
        df["_period"] = df["nam"].astype(str)

    period_cols = sorted(
        df["_period"].unique(),
        key=lambda p: (int(p.split("-Q")[0]), int(p.split("-Q")[1]))
        if "-Q" in p else (int(p), 0),
    )

    # ── Build extra-level config từ user toggles ───────────────────────────
    # (col_name in df, header label) tuples — order quyết định thứ tự hiển thị
    extra_cols: list[tuple[str, str]] = []
    if show_dt:
        extra_cols.append(("doi_tuong_giao_dich_kinh_te", "Đối tác"))
    if show_od:
        extra_cols.append(("phan_loai_on_dinh_khong_on_dinh", "Ổn định"))
    if show_nn:
        extra_cols.append(("phan_loai_ben_trong_ben_ngoai", "Nội/Ngoại"))
    extra_keys = [c[0] for c in extra_cols]

    # ── Pivot: index = (ma_don_vi, chi_tieu, *extras) ──────────────────────
    pivot_idx_cols = ["ma_don_vi", "chi_tieu"] + extra_keys
    pivot = df.pivot_table(
        index=pivot_idx_cols,
        columns="_period",
        values="so_tien_tong",
        aggfunc="sum",
        fill_value=0,
    ).reindex(columns=period_cols, fill_value=0)

    # Order: theo selection nếu có, ngược lại theo alphabetical từ pivot
    if sel_units:
        unit_order = sel_units
    else:
        unit_order = sorted(pivot.index.get_level_values(0).unique().tolist())

    # ── Build rows từ flat pivot ───────────────────────────────────────────
    # Mỗi row dict: {unit, ct, extras (list), values, is_net}
    pivot_flat = pivot.reset_index()
    rows: list[dict] = []
    for unit in unit_order:
        unit_subset = pivot_flat[pivot_flat["ma_don_vi"] == unit]
        if unit_subset.empty:
            continue
        for _, r in unit_subset.iterrows():
            rows.append({
                "unit": str(r["ma_don_vi"]),
                "ct": str(r["chi_tieu"]),
                "extras": [str(r[k]) for k in extra_keys],
                "values": [r[p] for p in period_cols],
                "is_net": False,
            })
        # Net row per đơn vị: sum across all sub-rows
        net_values = [unit_subset[p].sum() for p in period_cols]
        rows.append({
            "unit": unit,
            "ct": "Net",
            "extras": [""] * len(extra_keys),
            "values": net_values,
            "is_net": True,
        })

    if not show_net:
        rows = [r for r in rows if not r["is_net"]]

    if not rows:
        st.info("Không có dữ liệu với bộ lọc hiện tại.")
        return

    # Grand Total row — sum tất cả Net rows (chỉ có khi show_net = True)
    if show_net:
        net_rows = [r for r in rows if r["is_net"]]
        if net_rows:
            grand_values = [0.0] * len(period_cols)
            for r in net_rows:
                for i, v in enumerate(r["values"]):
                    if not pd.isna(v):
                        grand_values[i] += float(v)
            rows.append({
                "unit": "TỔNG CỘNG",
                "ct": "Net",
                "extras": [""] * len(extra_keys),
                "values": grand_values,
                "is_net": True,
                "is_grand": True,
            })

    # Append Tổng (row sum) tới mỗi row
    for r in rows:
        total = float(pd.Series(r["values"]).fillna(0).sum())
        r["values"] = list(r["values"]) + [total]

    # ── Compute rowspans (loại trừ grand row) ──────────────────────────────
    unit_counts: dict[str, int] = {}
    for r in rows:
        if r.get("is_grand"):
            continue
        unit_counts[r["unit"]] = unit_counts.get(r["unit"], 0) + 1

    # Loại giao dịch rowspan = số sub-rows trong (unit, ct) khi có extras
    ct_counts: dict[tuple[str, str], int] = {}
    if extra_cols:
        for r in rows:
            if r["is_net"]:
                continue
            key = (r["unit"], r["ct"])
            ct_counts[key] = ct_counts.get(key, 0) + 1

    # ── Build HTML ─────────────────────────────────────────────────────────
    unit_short = "triệu" if unit_label == "Triệu" else "tỷ"
    header_cells = [
        '<th class="hdr">Đơn vị</th>',
        f'<th class="hdr">Loại giao dịch ({unit_short} VNĐ)</th>',
    ]
    for _, lbl in extra_cols:
        header_cells.append(f'<th class="hdr">{lbl}</th>')
    header_cells += [f'<th class="hdr">{c}</th>' for c in period_cols]
    header_cells.append('<th class="hdr total-hdr">Tổng</th>')
    header_html = '<tr>' + "".join(header_cells) + '</tr>'

    body_rows = []
    seen_units: set[str] = set()
    seen_unit_ct: set[tuple[str, str]] = set()
    n_period = len(period_cols)
    n_extras = len(extra_cols)

    for r in rows:
        unit = r["unit"]
        ct = r["ct"]
        is_net = r["is_net"]
        is_grand = r.get("is_grand", False)
        values = r["values"]

        tr_class = (
            "grand-row" if is_grand
            else ("net-row" if is_net else "")
        )
        cells = []

        if is_grand:
            # Grand Total row: 1 cell colspan = 2 + n_extras gộp Đơn vị + ct + extras
            colspan_total = 2 + n_extras
            cells.append(
                f'<td class="grand-cell" colspan="{colspan_total}">'
                '<strong>TỔNG CỘNG (Σ Net)</strong></td>'
            )
            # Period values + Tổng — fall through xuống loop dưới
            for col_idx, v in enumerate(values):
                is_total_col = (col_idx == n_period)
                if pd.isna(v):
                    cls = "num grand-cell total-col" if is_total_col else "num grand-cell"
                    cells.append(f'<td class="{cls}">—</td>')
                    continue
                display_v = v / unit_divisor
                text = fmt_str.format(display_v)
                classes = ["num", "grand-cell"]
                if is_total_col:
                    classes.append("total-col")
                if show_format and v != 0:
                    classes.append("neg" if v < 0 else "pos")
                cells.append(f'<td class="{" ".join(classes)}">{text}</td>')
            body_rows.append(f'<tr class="{tr_class}">' + "".join(cells) + "</tr>")
            continue  # next row

        # Đơn vị (rowspan)
        if unit not in seen_units:
            seen_units.add(unit)
            cells.append(
                f'<td rowspan="{unit_counts[unit]}" class="unit-cell">{unit}</td>'
            )

        if is_net:
            # Net row: ct cell colspan = 1 + n_extras để merge ct + extras
            colspan = 1 + n_extras
            cells.append(
                f'<td class="ct-cell" colspan="{colspan}"><strong>Net</strong></td>'
            )
        else:
            if extra_cols:
                # Loại giao dịch (rowspan = số sub-rows trong (unit, ct))
                key = (unit, ct)
                if key not in seen_unit_ct:
                    seen_unit_ct.add(key)
                    cells.append(
                        f'<td rowspan="{ct_counts[key]}" class="ct-cell">{ct}</td>'
                    )
                # Extra cells (plain, no rowspan — repeat for each sub-row)
                for ev in r["extras"]:
                    cells.append(f'<td class="dt-cell">{ev}</td>')
            else:
                cells.append(f'<td class="ct-cell">{ct}</td>')

        # Period values + Tổng
        for col_idx, v in enumerate(values):
            is_total_col = (col_idx == n_period)
            if pd.isna(v):
                cls = "num total-col" if is_total_col else "num"
                cells.append(f'<td class="{cls}">—</td>')
                continue
            display_v = v / unit_divisor
            text = fmt_str.format(display_v)
            classes = ["num"]
            if is_total_col:
                classes.append("total-col")
            if show_format and v != 0:
                classes.append("neg" if v < 0 else "pos")
            cells.append(f'<td class="{" ".join(classes)}">{text}</td>')

        body_rows.append(f'<tr class="{tr_class}">' + "".join(cells) + "</tr>")

    css = """
    <style>
    .pivot-tbl { border-collapse: collapse; width: 100%; font-size: 12px;
                 font-family: 'Inter', 'Segoe UI', Roboto, sans-serif;
                 line-height: 1.2; }
    .pivot-tbl th, .pivot-tbl td { border: 1px solid #d9dfe6; padding: 3px 8px; }
    .pivot-tbl th.hdr { background: #f0f4f8; font-weight: 700; text-align: center; }
    .pivot-tbl th.total-hdr { background: #fff4d6; }
    .pivot-tbl td.unit-cell { background: #fdecea; font-weight: 700;
                              text-align: center; vertical-align: middle;
                              font-size: 13px; }
    .pivot-tbl td.ct-cell { text-align: left; font-weight: 600; }
    .pivot-tbl td.dt-cell { text-align: left; padding-left: 14px; color: #555;
                            font-size: 11px; }
    .pivot-tbl td.num { text-align: right; font-variant-numeric: tabular-nums; }
    .pivot-tbl td.total-col { background: #fffbe6; font-weight: 700; }
    .pivot-tbl tr.grand-row td.grand-cell {
        background: #2c3e50; color: white; font-weight: 700; font-size: 13px;
        text-align: center; padding: 5px 8px;
    }
    .pivot-tbl tr.grand-row td.grand-cell.num { text-align: right; }
    .pivot-tbl tr.grand-row td.grand-cell.total-col { background: #1a252f; }
    """
    if show_format:
        css += """
    .pivot-tbl .neg { color: #c0392b; font-weight: 600; }
    .pivot-tbl .pos { color: #1e8449; }
    .pivot-tbl tr.net-row td { background: #e3edf7; font-weight: 700; }
    .pivot-tbl tr.net-row td.total-col { background: #d9e7f3; }
    .pivot-tbl tr.grand-row td.grand-cell.neg { color: #ff7d6e; }
    .pivot-tbl tr.grand-row td.grand-cell.pos { color: #88e0a5; }
    """
    css += "</style>"

    pv_height = chart_height_slider(
        "p3_pv_height", default=520, min_v=300, max_v=800, step=20,
    )
    html = (
        css
        + f'<div style="overflow-x:auto;max-height:{pv_height}px;overflow-y:auto;">'
        + '<table class="pivot-tbl">'
        + "<thead>" + header_html + "</thead>"
        + "<tbody>" + "".join(body_rows) + "</tbody>"
        + "</table></div>"
    )
    st.markdown(html, unsafe_allow_html=True)
