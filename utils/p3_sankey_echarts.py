"""P3 Tab — Sankey ECharts (A/B test với p3_sankey.py Plotly).

Render Sankey qua ECharts CDN + st.components.v1.html (không cần
Python wrapper streamlit-echarts). Cùng VAS sign convention,
cùng filter UI (qua p3_sankey_common), key session state khác (`p3_ec_*`).
"""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from utils.charts import GEE_COLOR, GEL_COLOR, fmt_money_short
from utils.p3_sankey_common import render_sankey_filters_and_prepare
from utils.ui import chart_font_scale

_COLOR_POS = "rgba(39,174,96,0.55)"   # Thu
_COLOR_NEG = "rgba(231,76,60,0.55)"   # Chi
_EXTERNAL_COLOR = "#7f8c8d"
_HOLDING_COLOR = "#c0392b"            # GELEX (HOLDING) — đỏ
_ECHARTS_CDN = "https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"


def render(
    *,
    df_report: pd.DataFrame,
    nam_list: list[int],
    quy_list: list[int],
    nhom: str,
    unit_group: dict[str, str],
    ordered_labels: list[str],
    label_to_unit: dict[str, str],
) -> None:
    """Render Sankey tab in-place using ECharts."""
    data = render_sankey_filters_and_prepare(
        df_report=df_report, nam_list=nam_list, quy_list=quy_list,
        nhom=nhom, unit_group=unit_group,
        ordered_labels=ordered_labels, label_to_unit=label_to_unit,
        key_prefix="p3_ec",
    )
    if data is None:
        return
    sk = data.sk
    agg = data.agg

    # ── Build ECharts options ──────────────────────────────────────────────
    sources = agg["_src"].astype(str).tolist()
    targets = agg["_tgt"].astype(str).tolist()
    values = agg["so_tien_tong"].abs().tolist()
    raw_signs = agg["so_tien_tong"].tolist()
    all_nodes = sorted(set(sources) | set(targets))

    # Total inflow per node (chỉ tính ở target side)
    in_total: dict[str, float] = {}
    for tgt, v in zip(targets, values):
        in_total[tgt] = in_total.get(tgt, 0.0) + v

    # ECharts Sankey nodes — special-case GELEX (HOLDING) màu đỏ
    # TODO: thay bằng companies.csv type=HOLDING khi wire xong
    nodes_data = []
    for n in all_nodes:
        if n == "GELEX":
            color = _HOLDING_COLOR
        elif unit_group.get(n) == "GEE":
            color = GEE_COLOR
        elif unit_group.get(n) == "GEL":
            color = GEL_COLOR
        else:
            color = _EXTERNAL_COLOR
        if n in in_total:
            display_name = f"{n} ({fmt_money_short(in_total[n])})"
        else:
            display_name = n
        nodes_data.append({
            "name": display_name,
            "itemStyle": {"color": color, "borderColor": color},
        })

    name_map = {n: nd["name"] for n, nd in zip(all_nodes, nodes_data)}

    links_data = []
    for s, t, v, raw_v in zip(sources, targets, values, raw_signs):
        link_color = _COLOR_POS if raw_v > 0 else _COLOR_NEG
        links_data.append({
            "source": name_map[s],
            "target": name_map[t],
            "value": float(v),
            "lineStyle": {"color": link_color, "opacity": 0.55, "curveness": 0.5},
        })

    ec_font_scale = chart_font_scale("p3_ec_font")

    # Edge labels prepend "→" để chỉ direction (ECharts không có native arrowhead)
    for link in links_data:
        link["edgeLabel"] = {
            "show": True,
            "formatter": f"→ {fmt_money_short(link['value'])}",
            "fontSize": max(8, int(11 * ec_font_scale)),
            "fontWeight": "bold",
            "color": "#1a1a1a",
            "backgroundColor": "rgba(255,255,255,0.92)",
            "padding": [2, 6],
            "borderRadius": 3,
        }

    option = {
        "tooltip": {"trigger": "item", "triggerOn": "mousemove"},
        "series": [{
            "type": "sankey",
            "layout": "none",
            "data": nodes_data,
            "links": links_data,
            "draggable": True,
            "focusNodeAdjacency": True,
            "emphasis": {"focus": "adjacency"},
            "nodeAlign": "justify",
            "nodeGap": 12,
            "nodeWidth": 18,
            "label": {
                "show": True,
                "position": "right",
                "fontSize": max(8, int(12 * ec_font_scale)),
                "fontFamily": "Inter, 'Segoe UI', Roboto, sans-serif",
                "color": "#2c3e50",
            },
            "lineStyle": {"curveness": 0.5},
            "animationDuration": 500,
        }],
    }

    # ── Render via st.components.v1.html ───────────────────────────────────
    height = st.slider(
        "Chiều cao", min_value=400, max_value=800, value=600, step=50,
        key="p3_ec_height",
    )
    option_json = json.dumps(option, ensure_ascii=False)

    html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <script src="{_ECHARTS_CDN}"></script>
  <style>
    body {{ margin: 0; padding: 0; background: white; }}
    #chart {{ width: 100%; height: {height}px; }}
  </style>
</head>
<body>
  <div id="chart"></div>
  <script>
    var chart = echarts.init(document.getElementById('chart'));
    var option = {option_json};
    chart.setOption(option);
    window.addEventListener('resize', function() {{ chart.resize(); }});
  </script>
</body>
</html>
"""
    with st.container(border=True):
        components.html(html, height=height + 20)
        st.caption(
            "**ECharts Sankey** · Mũi tên = hướng tiền chảy thật (VAS) · "
            "**Xanh = Thu** · **Đỏ = Chi** · "
            "💡 Kéo node để rearrange · Hover để highlight adjacent links"
        )

    with st.expander(
        f"🔍 Xem dữ liệu gốc — {len(sk):,} rows raw, {len(agg):,} pairs sau aggregate"
    ):
        tab_raw, tab_agg = st.tabs(["Raw rows", "Aggregated pairs"])
        with tab_raw:
            raw_cols = [
                "ma_don_vi", "ten_don_vi", "code", "khoan_muc", "chi_tieu",
                "nam", "quy", "so_tien_tong",
                "phan_loai_on_dinh_khong_on_dinh",
                "phan_loai_ben_trong_ben_ngoai",
                "doi_tuong_giao_dich_kinh_te",
            ]
            st.dataframe(
                sk[[c for c in raw_cols if c in sk.columns]]
                .sort_values(["ma_don_vi", "doi_tuong_giao_dich_kinh_te", "nam", "quy"]),
                use_container_width=True, hide_index=True,
            )
        with tab_agg:
            st.dataframe(
                agg.sort_values("so_tien_tong", ascending=False),
                use_container_width=True, hide_index=True,
            )
