"""
ML Model Trainer.
Trains a RandomForestClassifier (with SMOTE balancing) for each coin
on historical 1-minute data and saves the model to disk.
"""

import os
import joblib
import numpy as np
import pandas as pd
from typing import Tuple, Optional
from loguru import logger
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from imblearn.over_sampling import SMOTE

from config import settings
from features.engineering import calculate_features, label_outcomes


def train_model_for_symbol(
    df_raw: pd.DataFrame,
    symbol: str,
) -> Optional[dict]:
    """
    Full training pipeline for a single symbol.
    1. Feature engineering
    2. Signal + outcome labeling
    3. SMOTE balancing
    4. RandomForest training
    5. Save model to disk

    Returns: dict with model, features, and performance stats, or None on failure.
    """
    logger.info(f"[{symbol}] Starting model training...")

    # ── Step 1: Feature Engineering ───────────────────────────────────────
    try:
        df = calculate_features(df_raw)
        df = label_outcomes(df)
    except Exception as e:
        logger.error(f"[{symbol}] Feature engineering failed: {e}")
        return None

    # ── Step 2: Prepare Training Data ─────────────────────────────────────
    mask = (df["Signal_Filtered"] != 0) & df["Outcome_Filtered"].notna()
    df_trades = df[mask].copy()

    if len(df_trades) < 30:
        logger.warning(f"[{symbol}] Only {len(df_trades)} labeled trades — not enough to train. Skipping.")
        return None

    features = settings.ML_FEATURES
    X = df_trades[features].copy()
    y = df_trades["Outcome_Filtered"].copy()

    # Handle NaN/Inf
    X.replace([np.inf, -np.inf], np.nan, inplace=True)
    X.ffill(inplace=True)
    X.fillna(0, inplace=True)

    logger.info(f"[{symbol}] Training samples: {len(X)} | Win rate: {y.mean():.2%}")

    # ── Step 3: Train/Test Split ───────────────────────────────────────────
    split_idx = int(len(X) * settings.TRAIN_TEST_SPLIT)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    if len(y_train.unique()) < 2:
        logger.warning(f"[{symbol}] Only one class in training data. Skipping SMOTE.")
        X_train_bal, y_train_bal = X_train, y_train
    else:
        # ── Step 4: SMOTE Balancing ────────────────────────────────────────
        try:
            smote = SMOTE(random_state=42, k_neighbors=min(5, y_train.value_counts().min() - 1))
            X_train_bal, y_train_bal = smote.fit_resample(X_train, y_train)
            logger.debug(f"[{symbol}] After SMOTE: {len(X_train_bal)} samples")
        except Exception as e:
            logger.warning(f"[{symbol}] SMOTE failed ({e}), using raw data.")
            X_train_bal, y_train_bal = X_train, y_train

    # ── Step 5: Train RandomForest ─────────────────────────────────────────
    model = RandomForestClassifier(
        n_estimators=settings.RF_N_ESTIMATORS,
        max_depth=settings.RF_MAX_DEPTH,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train_bal, y_train_bal)

    # ── Step 6: Evaluate ───────────────────────────────────────────────────
    if len(X_test) > 0:
        y_pred = model.predict(X_test)
        report = classification_report(y_test, y_pred, output_dict=True)
        test_winrate = float(report.get("1", {}).get("recall", 0.0))
        logger.info(f"[{symbol}] Test accuracy: {report.get('accuracy', 0):.2%} | Win recall: {test_winrate:.2%}")
    else:
        report = {}
        test_winrate = 0.0

    # ── Step 7: Save Model ─────────────────────────────────────────────────
    payload = {
        "model": model,
        "features": features,
        "symbol": symbol,
        "train_samples": len(X_train_bal),
        "test_winrate": test_winrate,
        "class_report": report,
        "feature_importance": dict(zip(features, model.feature_importances_)),
    }
    save_model(payload, symbol)

    logger.success(f"[{symbol}] [OK] Model trained and saved. Test win recall: {test_winrate:.2%}")
    return payload


def save_model(payload: dict, symbol: str):
    """Save model payload to disk."""
    os.makedirs(settings.MODELS_DIR, exist_ok=True)
    path = os.path.join(settings.MODELS_DIR, f"{symbol}.pkl")
    joblib.dump(payload, path)
    logger.debug(f"[{symbol}] Model saved to {path}")


def load_model(symbol: str) -> Optional[dict]:
    """Load a saved model from disk. Returns None if not found."""
    path = os.path.join(settings.MODELS_DIR, f"{symbol}.pkl")
    if not os.path.exists(path):
        return None
    try:
        payload = joblib.load(path)
        logger.debug(f"[{symbol}] Model loaded from {path}")
        return payload
    except Exception as e:
        logger.error(f"[{symbol}] Failed to load model: {e}")
        return None


def model_exists(symbol: str) -> bool:
    """Check if a trained model exists for this symbol."""
    path = os.path.join(settings.MODELS_DIR, f"{symbol}.pkl")
    return os.path.exists(path)


def list_trained_symbols() -> list:
    """Return list of symbols with trained models."""
    if not os.path.exists(settings.MODELS_DIR):
        return []
    return [
        f.replace(".pkl", "")
        for f in os.listdir(settings.MODELS_DIR)
        if f.endswith(".pkl")
    ]

