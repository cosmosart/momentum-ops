"""
⚡ Momentum Pulse — Streamlit native page.

Real-time monitoring and technical analysis for Korean equities
powered by the KIS (Korea Investment & Securities) REST API.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from dashboard.app import render_sidebar
from dashboard.momentum_pulse_tab import render_momentum_pulse_tab

ticker = render_sidebar(region_filter="KR", default_override="069500")

render_momentum_pulse_tab(ticker)
