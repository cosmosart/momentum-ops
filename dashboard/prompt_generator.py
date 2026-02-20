"""
LLM advisory prompt generator.

Compiles indicators, XGBoost probabilities, per-model SHAP contributions,
and portfolio mandates into a structured Markdown prompt ready to paste
into ChatGPT / Gemini / Claude.
"""

from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# Default portfolio mandates (can be overridden by caller)
# ---------------------------------------------------------------------------
DEFAULT_MANDATES: dict[str, str] = {
    "active": (
        "High-risk, high-reward. Focused on aggressive capital growth "
        "through short-term momentum trades (days to weeks)."
    ),
    "conservative": (
        "Low-risk, long-term wealth preservation. Focused on structural "
        "stability over a 5+ year horizon, ignoring daily volatility."
    ),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_llm_advisory_prompt(
    ticker: str,
    quant_data_df: pd.DataFrame,
    xgboost_results: dict[str, dict],
    mandates: dict[str, str] | None = None,
    language: str = "English",
) -> str:
    """
    Generate a structured prompt for LLM-based financial advisory.

    Parameters
    ----------
    ticker : str
        The asset ticker symbol (e.g. ``"GOOGL"``, ``"005930.KS"``).
    quant_data_df : pd.DataFrame
        DataFrame with columns ``["Indicator", "Value"]`` containing the
        latest technical indicator snapshots.
    xgboost_results : dict[str, dict]
        Keyed by model name.  Each value is a dict with:
        - ``"label"``  : human-readable model name (str)
        - ``"prob"``   : directional probability (float | None)
        - ``"shap_df"`` : DataFrame ``["Feature", "SHAP Value", "Direction"]``
                          or ``None`` if contributions are unavailable.
    mandates : dict[str, str] | None
        ``{"active": "...", "conservative": "..."}``.
        Falls back to ``DEFAULT_MANDATES`` when *None*.
    language : str
        Target language for the LLM response (e.g. ``"English"``,
        ``"Korean"``, ``"Japanese"``).

    Returns
    -------
    str
        Ready-to-paste Markdown prompt.
    """
    if mandates is None:
        mandates = DEFAULT_MANDATES

    # ------------------------------------------------------------------
    # Section 1 — The Request
    # ------------------------------------------------------------------
    section_1 = f"""## 1. The Request
Act as an expert quantitative financial advisor. Based on the following technical data, my specific portfolio mandates, and real-time market conditions, provide:
1. A projected price range for the **short-term** (1-week), **mid-term** (1-to-6 months), **long-term** (1-year), and **structural** (3-year+) horizons for **{ticker}**.
2. A definitive personalized decision (**Buy / Hold / Sell**) for both my **Active** and **Conservative** portfolios.
3. **CRITICAL STEP:** Before generating your response, you must **search the web** for the latest news, earnings reports, macroeconomic trends, and sector-specific catalysts affecting {ticker}. Integrate this real-world context with the quantitative signals below.
"""

    # ------------------------------------------------------------------
    # Section 2 — Quantitative Data
    # ------------------------------------------------------------------
    quant_table = quant_data_df.to_markdown(index=False, tablefmt="pipe")
    section_2 = f"""## 2. Quantitative Data (Technical Indicators)
{quant_table}
"""

    # ------------------------------------------------------------------
    # Section 3 — XGBoost Probabilities & SHAP
    # ------------------------------------------------------------------
    model_blocks: list[str] = []
    for model_key, result in xgboost_results.items():
        label = result["label"]
        prob = result.get("prob")
        shap_df = result.get("shap_df")

        prob_str = f"{prob:.2%}" if prob is not None else "N/A"
        block = f"### {label}\n- **Model Confidence (Bullish):** {prob_str}\n"

        if shap_df is not None and not shap_df.empty:
            shap_table = shap_df.to_markdown(index=False, tablefmt="pipe")
            block += f"- **Top SHAP Contributors:**\n\n{shap_table}\n"
        else:
            block += "- **Top SHAP Contributors:** _(not yet available)_\n"

        model_blocks.append(block)

    section_3 = "## 3. Machine Learning Signals (XGBoost)\n\n" + "\n".join(model_blocks)

    # ------------------------------------------------------------------
    # Section 4 — Strategic Context
    # ------------------------------------------------------------------
    section_4 = f"""## 4. Strategic Context & Mandates
Evaluate this asset against two distinct portfolio strategies:

- **Active Portfolio:** {mandates['active']}
- **Conservative Portfolio:** {mandates['conservative']}

_Please structure your response with clear headings for each portfolio strategy and include specific price targets where possible._
"""

    # ------------------------------------------------------------------
    # Assemble
    # ------------------------------------------------------------------
    header = f"# AI Advisory Prompt — {ticker}\n"

    # Language instruction (appended at the very end)
    lang_instruction = ""
    if language and language != "English":
        lang_instruction = (
            f"\n---\n\n"
            f"**⚠️ LANGUAGE REQUIREMENT:** You MUST write your entire response "
            f"in **{language}**. All headings, analysis, and recommendations "
            f"must be in {language}.\n"
        )

    return f"{header}\n---\n\n{section_1}\n---\n\n{section_2}\n---\n\n{section_3}\n---\n\n{section_4}{lang_instruction}"
