"""
🎯 Directional Outlook — Streamlit native page.

Displays XGBoost directional-probability scores from four strategy models
and the SHAP feature contributions behind each prediction.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Ensure repo root is importable
_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from dashboard.app import render_sidebar  # shared sidebar
from dashboard.predictions_tab import render_predictions_tab

# ── Sidebar (shared across all pages) ────────────────────────────────────
ticker = render_sidebar()

# ── Page content ──────────────────────────────────────────────────────────
render_predictions_tab(ticker)
