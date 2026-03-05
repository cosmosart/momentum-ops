"""
📊 Momentum Analysis — Streamlit native page.

Displays RSI, MACD, and Bollinger Band technical indicator charts for
the selected ticker.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from dashboard.app import render_sidebar
from dashboard.momentum_tab import render_momentum_tab

ticker = render_sidebar()

render_momentum_tab(ticker)
