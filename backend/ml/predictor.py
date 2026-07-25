"""
Live ML Predictor.
Uses the trained RandomForest model to predict win probability for each new signal.
"""

import numpy as np
import pandas as pd
from typing import Optional, Tuple
from loguru import logger

from config import settings
from ml.trainer import load_model


class LivePredictor:
    """
    Manages loaded models and makes real-time predictions.
    Each symbol has its own model instance cached in memory.
    """

    def __init__(self):
        self._models: dict = {}  # symbol → model payload

    def load(self, symbol: str) -> bool:
        """Load the model for a symbol into memory. Returns True if successful."""
        payload = load_model(symbol)
        if payload is None:
            logger.warning(f"[{symbol}] No trained model found.")
            return False
        self._models[symbol] = payload
        logger.debug(f"[{symbol}] Predictor ready.")
        return True

    def is_ready(self, symbol: str) -> bool:
        return symbol in self._models

    def predict(self, symbol: str, feature_row: dict) -> Tuple[float, bool]:
        """
        Predict win probability for the latest signal.

        Args:
            symbol: Trading pair, e.g. 'BTCUSDT'
            feature_row: Dict of {feature_name: value}

        Returns:
            (win_probability, should_trade) tuple
            should_trade is True if win_prob > threshold
        """
        if symbol not in self._models:
            loaded = self.load(symbol)
            if not loaded:
                return 0.0, False

        payload = self._models[symbol]
        model = payload["model"]
        features = payload["features"]

        # Build feature vector
        try:
            X = pd.DataFrame([{f: feature_row.get(f, 0.0) for f in features}])
            X.replace([np.inf, -np.inf], np.nan, inplace=True)
            X.ffill(inplace=True)
            X.fillna(0, inplace=True)

            win_prob = float(model.predict_proba(X)[:, 1][0])
            should_trade = win_prob >= settings.WIN_PROB_THRESHOLD

            return win_prob, should_trade

        except Exception as e:
            logger.error(f"[{symbol}] Prediction error: {e}")
            return 0.0, False

    def get_feature_importance(self, symbol: str) -> dict:
        """Return feature importance dict for a symbol."""
        if symbol not in self._models:
            return {}
        return self._models[symbol].get("feature_importance", {})

    def unload(self, symbol: str):
        """Remove a model from memory."""
        self._models.pop(symbol, None)

    def loaded_symbols(self) -> list:
        return list(self._models.keys())


# Global predictor instance
predictor = LivePredictor()

