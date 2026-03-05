"""
🤖 AI Advisor — Streamlit native page.

Generates structured LLM prompts (ChatGPT / Gemini / Claude) from the
latest analysis data for secondary human-in-the-loop review.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from dashboard.app import render_sidebar
from dashboard.ai_advisor_tab import render_ai_advisor_tab

ticker = render_sidebar()

render_ai_advisor_tab(ticker)
