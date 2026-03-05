"""
⚙️ Manage Tickers — Streamlit native page.

Add, deactivate, and review tracked ticker symbols.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from dashboard.app import render_sidebar
from dashboard.ticker_management_tab import render_ticker_management

_ = render_sidebar()

render_ticker_management()
