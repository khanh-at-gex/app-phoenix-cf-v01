"""Small HTML / Streamlit UI helpers."""
from __future__ import annotations

import streamlit as st


def badge(text: str, color: str, font_size: str = "12px") -> str:
    """Pill-shaped colored HTML badge for st.markdown(unsafe_allow_html=True)."""
    return (
        f'<span style="background:{color};color:white;padding:2px 8px;'
        f'border-radius:12px;font-size:{font_size};margin:2px;display:inline-block">'
        f"{text}</span>"
    )


def chart_height_slider(
    key: str,
    default: int = 520,
    min_v: int = 300,
    max_v: int = 800,
    step: int = 20,
    label: str = "Chiều cao",
) -> int:
    """
    Render Streamlit slider điều chỉnh chiều cao chart.
    Tự clamp `default` vào [min_v, max_v].
    """
    safe_default = max(min_v, min(max_v, int(default)))
    return st.slider(
        label, min_value=min_v, max_value=max_v,
        value=safe_default, step=step, key=key,
    )
