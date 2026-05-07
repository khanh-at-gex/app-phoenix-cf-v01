"""Small HTML helpers used with st.markdown(unsafe_allow_html=True)."""
from __future__ import annotations


def badge(text: str, color: str, font_size: str = "12px") -> str:
    """Pill-shaped colored badge."""
    return (
        f'<span style="background:{color};color:white;padding:2px 8px;'
        f'border-radius:12px;font-size:{font_size};margin:2px;display:inline-block">'
        f"{text}</span>"
    )
