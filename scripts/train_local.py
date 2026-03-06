#!/usr/bin/env python3
"""
Local XGBoost training script for the directional-probability pipeline.

Designed to run on a workstation with an NVIDIA GPU (e.g. RTX 3070).
Reads historical daily prices from the PostgreSQL database (or a CSV dump),
engineers features via the shared `models.features` module, trains an
XGBoost binary classifier, and saves artefacts with the EXACT filenames that
``MODEL_REGISTRY`` in ``models/models.py`` expects — no manual rename needed.

Usage
-----
    # Train ALL 4 models (default):
    python scripts/train_local.py

    # Train specific model(s) by registry key:
    python scripts/train_local.py --models active_1w experimental

    # Use a CSV dump instead of PostgreSQL:
    python scripts/train_local.py --csv data/dump.csv --models conservative_1mo

    # With Optuna hyperparameter search:
    python scripts/train_local.py --tune --tune-trials 200

    # Single model with tuning:
    python scripts/train_local.py --models active_1w --tune

Artefact naming (driven by MODEL_REGISTRY):
    active_1w         → xgboost_active_1w.json         + xgboost_threshold_active_1w.json
    conservative_1mo  → xgboost_conservative_1mo.json   + xgboost_threshold_conservative_1mo.json
    conservative_6mo  → xgboost_conservative_6mo.json   + xgboost_threshold_conservative_6mo.json
    experimental      → xgboost_experimental.json       + xgboost_threshold_experimental.json

Environment variables for DB connection (loaded from .env):
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import numpy as np.
import pandas as pd
from dotenv import load_dotenv
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    f1_score,
    log_loss,
    precision_recall_curve,
    roc_auc_score,
)
import optuna
import xgboost as xgb

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path so we can import `models.features`
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.features import (  # noqa: E402
    FEATURE_COLUMNS,
    HORIZONS,
    engineer_features,
    make_target,
)
from models.models import MODEL_REGISTRY  # noqa: E402

# ---------------------------------------------------------------------------
# Training plan — maps each MODEL_REGISTRY key to the horizon used for
# target construction.  This is the single source of truth that keeps
# train_local.py aligned with what the inference container loads.
# ---------------------------------------------------------------------------
TRAINING_PLAN: dict[str, str] = {
    "active_1w":        "1w",
    "conservative_1mo": "1mo",
    "conservative_6mo": "6mo",
    "experimental":     "1d",   # next-business-day directional prediction
}

# ---------------------------------------------------------------------------
# Per-model default hyperparameter profiles.
# Models NOT listed here use the shared defaults in train_xgboost().
# The experimental slot deliberately overfits — deep trees, no regularisation,
# no subsampling — to squeeze maximum signal out of the 1-day horizon.
# ---------------------------------------------------------------------------
MODEL_DEFAULTS: dict[str, dict] = {
    "experimental": dict(
        n_estimators=2000,
        max_depth=12,
        learning_rate=0.1,
        subsample=1.0,
        colsample_bytree=1.0,
        colsample_bylevel=1.0,
        min_child_weight=1,
        gamma=0.0,
        reg_alpha=0.0,
        reg_lambda=0.0,
        early_stopping_rounds=None,   # no early stopping — full memorisation
    ),
}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv(PROJECT_ROOT / ".env")

MODEL_OUTPUT_DIR = PROJECT_ROOT / "model_artifacts"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("train_local")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_from_database() -> pd.DataFrame:
    """
    Fetch all daily prices for every active ticker from PostgreSQL.

    Returns a DataFrame with columns: ticker, date, Open, High, Low, Close, Volume.
    """
    import psycopg

    conn_params = dict(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "momentum_db"),
        user=os.getenv("DB_USER", "momentum_user"),
        password=os.getenv("DB_PASSWORD", "momentum_password"),
    )

    logger.info("Connecting to PostgreSQL at %s:%s/%s …", conn_params["host"], conn_params["port"], conn_params["dbname"])

    with psycopg.connect(**conn_params) as conn:
        query = """
            SELECT
                pd.ticker,
                pd.region,
                pd.date,
                pd.open   AS "Open",
                pd.high   AS "High",
                pd.low    AS "Low",
                pd.close  AS "Close",
                pd.volume AS "Volume"
            FROM price_daily pd
            JOIN tickers t ON t.symbol = pd.ticker AND t.is_active = true
            ORDER BY pd.ticker, pd.date
        """
        df = pd.read_sql(query, conn)

    logger.info("Loaded %d rows for %d tickers from database", len(df), df["ticker"].nunique())
    return df


def load_from_csv(csv_path: str) -> pd.DataFrame:
    """
    Load daily price data from a CSV file.

    Expected columns (case-insensitive matching):
        ticker, date, Open, High, Low, Close, Volume
    """
    logger.info("Loading data from CSV: %s", csv_path)
    df = pd.read_csv(csv_path, parse_dates=["date"])

    # Normalize column names
    col_map = {c: c for c in df.columns}
    for c in df.columns:
        lower = c.lower()
        if lower == "open":
            col_map[c] = "Open"
        elif lower == "high":
            col_map[c] = "High"
        elif lower == "low":
            col_map[c] = "Low"
        elif lower == "close":
            col_map[c] = "Close"
        elif lower == "volume":
            col_map[c] = "Volume"
    df.rename(columns=col_map, inplace=True)

    logger.info("Loaded %d rows for %d tickers from CSV", len(df), df["ticker"].nunique())
    return df


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def build_dataset(
    raw_df: pd.DataFrame,
    horizon: int = 5,
    hurdle: float = 0.015,
) -> tuple[pd.DataFrame, pd.Series, float]:
    """
    Apply feature engineering and target creation per-ticker, then concatenate.

    Returns (X, y, scale_pos_weight) with NaN rows already dropped.
    ``scale_pos_weight`` is ``count(neg) / count(pos)`` — used to compensate
    for the class imbalance introduced by the hurdle.

    Parameters
    ----------
    raw_df : pd.DataFrame
        Raw OHLCV data with a ``ticker`` column.
    horizon : int
        Forward window in trading days.
    hurdle : float
        Minimum return threshold to label as "Up".
    """
    all_X: list[pd.DataFrame] = []
    all_y: list[pd.Series] = []

    for ticker, group in raw_df.groupby("ticker"):
        group = group.sort_values("date").reset_index(drop=True)

        if len(group) < 60:
            logger.warning("Skipping %s — only %d rows (need >= 60)", ticker, len(group))
            continue

        features = engineer_features(group)
        target = make_target(group, horizon=horizon, hurdle=hurdle)

        # Combine, drop any row with NaN in features OR target
        combined = pd.concat([features, target], axis=1)
        combined.dropna(inplace=True)

        if combined.empty:
            logger.warning("Skipping %s — no valid rows after NaN removal", ticker)
            continue

        all_X.append(combined[FEATURE_COLUMNS])
        all_y.append(combined["target"])
        logger.info("  %s  →  %d samples (%.1f%% positive)", ticker, len(combined), combined["target"].mean() * 100)

    if not all_X:
        raise RuntimeError("No usable data after feature engineering. Aborting.")

    X = pd.concat(all_X, ignore_index=True)
    y = pd.concat(all_y, ignore_index=True)

    logger.info("Total dataset: %d samples, %.1f%% positive class", len(X), y.mean() * 100)

    # Dynamic class-imbalance weight
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    spw = n_neg / max(n_pos, 1)
    logger.info("Class balance — neg: %d  pos: %d  scale_pos_weight: %.3f", n_neg, n_pos, spw)

    return X, y, spw


# ---------------------------------------------------------------------------
# Hyperparameter tuning (Optuna)
# ---------------------------------------------------------------------------

def _detect_device() -> str:
    """Probe for CUDA availability and return 'cuda' or 'cpu'."""
    try:
        _dmat = xgb.DMatrix(np.zeros((2, 2)), label=[0, 1])
        xgb.train({"tree_method": "hist", "device": "cuda"}, _dmat, num_boost_round=1)
        return "cuda"
    except xgb.core.XGBoostError:
        return "cpu"


def _find_optimal_threshold(
    y_true: pd.Series | np.ndarray,
    proba: np.ndarray,
) -> float:
    """
    Sweep thresholds on the precision-recall curve and return the one that
    maximises the F1-score.  Falls back to 0.5 if the curve is degenerate.
    """
    precision, recall, thresholds = precision_recall_curve(y_true, proba)
    # precision_recall_curve returns len(thresholds) = len(precision) - 1
    f1_scores = (
        2 * (precision[:-1] * recall[:-1])
        / (precision[:-1] + recall[:-1] + 1e-12)
    )
    if len(f1_scores) == 0:
        return 0.5
    best_idx = int(np.argmax(f1_scores))
    return float(thresholds[best_idx])


def tune_hyperparameters(
    X: pd.DataFrame,
    y: pd.Series,
    scale_pos_weight: float,
    n_trials: int = 100,
    cv_splits: int = 5,
    timeout: int | None = None,
) -> dict:
    """
    Run Optuna Bayesian optimisation over the XGBoost hyperparameter space.

    Uses walk-forward ``TimeSeriesSplit`` so that future data never leaks into
    training folds.  The objective maximises mean ROC-AUC across folds.

    Parameters
    ----------
    X : pd.DataFrame
        Feature matrix.
    y : pd.Series
        Binary target.
    scale_pos_weight : float
        Data-driven class-imbalance weight (neg / pos).  The search range is
        centred around this value ± 50 %.
    n_trials : int
        Number of Optuna trials (default 100).
    cv_splits : int
        Number of TimeSeriesSplit folds (default 5).
    timeout : int or None
        Optional wall-clock time limit in seconds.

    Returns
    -------
    dict
        Best hyperparameter dict ready to unpack into ``XGBClassifier``.
    """
    device = _detect_device()
    logger.info("Starting Optuna hyperparameter search (%d trials, device=%s) …", n_trials, device)

    tscv = TimeSeriesSplit(n_splits=cv_splits)

    def objective(trial: optuna.Trial) -> float:
        params = {
            # Boosting rounds (early-stopped, so overshoot is fine)
            "n_estimators":      trial.suggest_int("n_estimators", 200, 2000, step=100),
            # Tree structure
            "max_depth":         trial.suggest_int("max_depth", 3, 10),
            "min_child_weight":  trial.suggest_int("min_child_weight", 1, 20),
            "max_leaves":        trial.suggest_int("max_leaves", 0, 256, step=8),
            # Learning rate (log-uniform)
            "learning_rate":     trial.suggest_float("learning_rate", 0.005, 0.3, log=True),
            # Sampling
            "subsample":         trial.suggest_float("subsample", 0.5, 1.0, step=0.05),
            "colsample_bytree":  trial.suggest_float("colsample_bytree", 0.3, 1.0, step=0.05),
            "colsample_bylevel": trial.suggest_float("colsample_bylevel", 0.3, 1.0, step=0.05),
            # Regularisation
            "gamma":             trial.suggest_float("gamma", 0.0, 5.0),
            "reg_alpha":         trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
            "reg_lambda":        trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
            # Scale positive weights — centred on the empirical ratio
            "scale_pos_weight":  trial.suggest_float(
                "scale_pos_weight",
                max(0.5, scale_pos_weight * 0.5),
                scale_pos_weight * 1.5,
            ),
            # Fixed
            "tree_method":       "hist",
            "device":            device,
            "objective":         "binary:logistic",
            "eval_metric":       "aucpr",
            "random_state":      42,
            "n_jobs":            -1,
            "early_stopping_rounds": 30,
        }

        fold_scores: list[float] = []
        for train_idx, val_idx in tscv.split(X):
            X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_tr, y_val = y.iloc[train_idx], y.iloc[val_idx]

            clf = xgb.XGBClassifier(**params)
            clf.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)

            proba = clf.predict_proba(X_val)[:, 1]
            fold_scores.append(average_precision_score(y_val, proba))

        mean_auc = float(np.mean(fold_scores))

        # Report intermediate value so Optuna can prune bad trials early
        trial.report(mean_auc, step=0)
        if trial.should_prune():
            raise optuna.TrialPruned()

        return mean_auc

    # --- Run study ---------------------------------------------------------
    study = optuna.create_study(
        direction="maximize",
        study_name="xgb_direction",
        pruner=optuna.pruners.MedianPruner(n_warmup_steps=10),
    )
    study.optimize(objective, n_trials=n_trials, timeout=timeout, show_progress_bar=True)

    best = study.best_trial
    logger.info("Optuna finished — best PR-AUC: %.4f  (trial #%d)", best.value, best.number)
    logger.info("Best params: %s", best.params)

    # Merge fixed params with tuned params
    best_params = {
        **best.params,
        "tree_method":  "hist",
        "device":       device,
        "objective":    "binary:logistic",
        "eval_metric":  "aucpr",
        "random_state":  42,
        "n_jobs":        -1,
        "early_stopping_rounds": 30,
    }
    return best_params


# ---------------------------------------------------------------------------
# Train
# ---------------------------------------------------------------------------

def train_xgboost(
    X: pd.DataFrame,
    y: pd.Series,
    scale_pos_weight: float,
    params: dict | None = None,
    model_key: str | None = None,
) -> tuple[xgb.XGBClassifier, float]:
    """
    Train an XGBoost binary classifier with GPU acceleration and
    time-series-aware cross-validation.

    Parameters
    ----------
    X : pd.DataFrame  — feature matrix (FEATURE_COLUMNS)
    y : pd.Series     — binary target
    scale_pos_weight : float
        Data-driven class weight (default 1.0, overridden by ``build_dataset``).
    params : dict, optional
        Pre-tuned hyperparameters (e.g. from ``tune_hyperparameters``).
        When *None*, sensible defaults are used.
    model_key : str, optional
        MODEL_REGISTRY key (e.g. ``"experimental"``).  When provided and
        ``params`` is None, per-model overrides from ``MODEL_DEFAULTS``
        are applied on top of the shared defaults.

    Returns
    -------
    (xgb.XGBClassifier, float)
        Fitted model and the optimal classification threshold (maximises F1).
    """
    # ------------------------------------------------------------------
    # Build parameter dict — tuned params override defaults
    # ------------------------------------------------------------------
    device = _detect_device()
    logger.info("Device: %s", device)

    if params is not None:
        logger.info("Using Optuna-tuned hyperparameters")
        model_params = {**params, "device": device}
    else:
        # Shared conservative defaults
        model_params = dict(
            n_estimators=500,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=5,
            gamma=0.1,
            reg_alpha=0.1,
            reg_lambda=1.0,
            scale_pos_weight=scale_pos_weight,
            tree_method="hist",
            device=device,
            objective="binary:logistic",
            eval_metric="aucpr",
            random_state=42,
            n_jobs=-1,
            early_stopping_rounds=30,
        )
        # Apply per-model overrides (e.g. experimental → overfit profile)
        if model_key and model_key in MODEL_DEFAULTS:
            overrides = MODEL_DEFAULTS[model_key]
            model_params.update(overrides)
            logger.info(
                "Applied MODEL_DEFAULTS['%s'] overrides: %s",
                model_key,
                ", ".join(f"{k}={v}" for k, v in overrides.items()),
            )

    # Resolve early_stopping_rounds=None → remove the key entirely so
    # XGBClassifier trains for the full n_estimators without stopping.
    use_early_stopping = model_params.get("early_stopping_rounds") is not None
    if not use_early_stopping:
        model_params.pop("early_stopping_rounds", None)

    model = xgb.XGBClassifier(**model_params)

    # ------------------------------------------------------------------
    # Time-series cross-validation (walk-forward)
    # ------------------------------------------------------------------
    tscv = TimeSeriesSplit(n_splits=5)
    cv_scores: list[dict] = []

    logger.info("Running 5-fold TimeSeriesSplit cross-validation …")
    for fold, (train_idx, val_idx) in enumerate(tscv.split(X), start=1):
        X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_tr, y_val = y.iloc[train_idx], y.iloc[val_idx]

        model.fit(
            X_tr,
            y_tr,
            eval_set=[(X_val, y_val)] if use_early_stopping else None,
            verbose=False,
        )

        proba = model.predict_proba(X_val)[:, 1]
        thr = _find_optimal_threshold(y_val, proba)
        preds = (proba >= thr).astype(int)

        fold_metrics = {
            "fold": fold,
            "threshold": thr,
            "f1": f1_score(y_val, preds, zero_division=0),
            "accuracy": accuracy_score(y_val, preds),
            "roc_auc": roc_auc_score(y_val, proba),
            "pr_auc": average_precision_score(y_val, proba),
        }
        cv_scores.append(fold_metrics)
        logger.info(
            "  Fold %d — Thr: %.3f | F1: %.4f | AUC: %.4f | PR-AUC: %.4f",
            fold,
            thr,
            fold_metrics["f1"],
            fold_metrics["roc_auc"],
            fold_metrics["pr_auc"],
        )

    # Summary
    mean_f1 = np.mean([s["f1"] for s in cv_scores])
    mean_auc = np.mean([s["roc_auc"] for s in cv_scores])
    mean_pr_auc = np.mean([s["pr_auc"] for s in cv_scores])
    logger.info("CV mean — F1: %.4f | AUC: %.4f | PR-AUC: %.4f", mean_f1, mean_auc, mean_pr_auc)

    # ------------------------------------------------------------------
    # Final fit on full dataset
    # ------------------------------------------------------------------
    logger.info("Fitting final model on full dataset (%d samples) …", len(X))

    # Use last 10% as eval set for early stopping on final fit
    split_point = int(len(X) * 0.9)
    X_train_final, X_eval_final = X.iloc[:split_point], X.iloc[split_point:]
    y_train_final, y_eval_final = y.iloc[:split_point], y.iloc[split_point:]

    model.fit(
        X_train_final,
        y_train_final,
        eval_set=[(X_eval_final, y_eval_final)] if use_early_stopping else None,
        verbose=False,
    )

    # Report final metrics on the hold-out eval set
    final_proba = model.predict_proba(X_eval_final)[:, 1]
    optimal_threshold = _find_optimal_threshold(y_eval_final, final_proba)
    final_preds = (final_proba >= optimal_threshold).astype(int)
    logger.info("Optimal classification threshold: %.3f", optimal_threshold)
    logger.info("Final hold-out metrics:")
    logger.info("\n%s", classification_report(y_eval_final, final_preds, target_names=["Down/Flat", "Up"]))

    return model, optimal_threshold


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _derive_threshold_filename(model_filename: str) -> str:
    """
    Given a model filename like ``xgboost_active_1w.json``, return the
    matching threshold sidecar name ``xgboost_threshold_active_1w.json``.

    Mirrors the lookup logic in ``DirectionPredictor._load_model()``.
    """
    return "xgboost_threshold_" + model_filename.removeprefix("xgboost_")


def main() -> None:
    all_keys = list(TRAINING_PLAN.keys())

    parser = argparse.ArgumentParser(
        description="Train XGBoost directional-probability models locally.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Train ALL 4 models:\n"
            "  python scripts/train_local.py\n\n"
            "  # Train specific model(s):\n"
            "  python scripts/train_local.py --models active_1w experimental\n\n"
            "  # With Optuna hyperparameter tuning:\n"
            "  python scripts/train_local.py --models active_1w --tune\n\n"
            "  # Tune all models (200 trials, 30 min timeout each):\n"
            "  python scripts/train_local.py --tune --tune-trials 200 --tune-timeout 1800\n"
        ),
    )
    parser.add_argument(
        "--models",
        nargs="*",
        choices=all_keys,
        default=None,
        help=(
            "Which models to train (MODEL_REGISTRY keys): "
            + ", ".join(all_keys)
            + ".  Omit to train ALL 4."
        ),
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Path to a CSV dump of daily prices (skips database read).",
    )
    parser.add_argument(
        "--tune",
        action="store_true",
        default=False,
        help="Run Optuna Bayesian hyperparameter search before final training.",
    )
    parser.add_argument(
        "--tune-trials",
        type=int,
        default=100,
        help="Number of Optuna trials (default: 100).",
    )
    parser.add_argument(
        "--tune-timeout",
        type=int,
        default=None,
        help="Wall-clock time limit for tuning in seconds (optional).",
    )
    args = parser.parse_args()

    # --- Resolve which models to train ------------------------------------
    selected_keys = args.models or all_keys

    logger.info(
        "Training plan — models: %s  (%d total)",
        ", ".join(selected_keys),
        len(selected_keys),
    )
    for key in selected_keys:
        horizon_key = TRAINING_PLAN[key]
        trading_days, hurdle = HORIZONS[horizon_key]
        logger.info(
            "  %s  →  horizon=%s (%d days, hurdle %.1f%%)  →  %s",
            key, horizon_key, trading_days, hurdle * 100, MODEL_REGISTRY[key],
        )

    # 1. Load data ONCE — shared across all models
    if args.csv:
        raw_df = load_from_csv(args.csv)
    else:
        raw_df = load_from_database()

    MODEL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- Loop: one iteration per MODEL_REGISTRY key -----------------------
    for idx, key in enumerate(selected_keys, start=1):
        horizon_key = TRAINING_PLAN[key]
        trading_days, hurdle = HORIZONS[horizon_key]
        model_filename = MODEL_REGISTRY[key]
        threshold_filename = _derive_threshold_filename(model_filename)

        logger.info(
            "\n" + "#" * 72
            + "\n##  [%d/%d]  Model: %s  (horizon=%s, %d days, hurdle %.1f%%)\n"
            + "#" * 72,
            idx, len(selected_keys), key, horizon_key, trading_days, hurdle * 100,
        )

        # 2. Build feature matrix + target for this horizon
        X, y, spw = build_dataset(raw_df, horizon=trading_days, hurdle=hurdle)

        # 3. (Optional) Hyperparameter search
        best_params: dict | None = None
        if args.tune:
            best_params = tune_hyperparameters(
                X, y,
                scale_pos_weight=spw,
                n_trials=args.tune_trials,
                timeout=args.tune_timeout,
            )

        # 4. Train with best (or default) params
        model, threshold = train_xgboost(
            X, y, scale_pos_weight=spw, params=best_params, model_key=key,
        )

        # 5. Save model artefact + threshold sidecar
        #    Filenames are EXACTLY what MODEL_REGISTRY declares.
        model_path = MODEL_OUTPUT_DIR / model_filename
        threshold_path = MODEL_OUTPUT_DIR / threshold_filename

        model.save_model(str(model_path))
        logger.info("Model saved → %s", model_path)

        threshold_meta = {
            "registry_key": key,
            "horizon": horizon_key,
            "trading_days": trading_days,
            "hurdle": hurdle,
            "threshold": round(threshold, 4),
            "scale_pos_weight": round(spw, 4),
            "positive_class_pct": round(float(y.mean()) * 100, 2),
        }
        threshold_path.write_text(json.dumps(threshold_meta, indent=2))
        logger.info("Threshold (%.3f) saved → %s", threshold, threshold_path)

        # 6. Quick sanity check: reload and predict a single row
        loaded = xgb.XGBClassifier()
        loaded.load_model(str(model_path))
        sample_proba = loaded.predict_proba(X.tail(1))[:, 1][0]
        logger.info(
            "Sanity check — last row P(Up): %.4f → %s (threshold %.3f)",
            sample_proba,
            "Up" if sample_proba >= threshold else "Down/Flat",
            threshold,
        )

    # --- Summary ----------------------------------------------------------
    logger.info("\n" + "=" * 72)
    logger.info("Training complete!")
    logger.info("Artifacts saved to: %s", MODEL_OUTPUT_DIR)
    logger.info("Models trained: %d", len(selected_keys))
    for key in selected_keys:
        logger.info("  %-20s → %s", key, MODEL_REGISTRY[key])
    logger.info("=" * 72)


if __name__ == "__main__":
    main()
