"""
AML Data Preprocessor
=======================
Scikit-learn compatible preprocessing pipeline for AML transaction and
customer feature data. Handles missing values, categorical encoding,
feature scaling, and temporal feature extraction.

Usage:
    from ml.data_preprocessor import AMLDataPreprocessor
    import json

    preprocessor = AMLDataPreprocessor()
    X_train = preprocessor.fit_transform(df_train)
    X_test = preprocessor.transform(df_test)
    preprocessor.save("models/preprocessor.json")
"""

import json
import math
import logging
import statistics
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Type alias for a row dict
RowType = Dict[str, Any]
DatasetType = List[RowType]


class AMLDataPreprocessor:
    """
    Full preprocessing pipeline for AML feature data.

    Handles:
      - Missing value imputation (median for numeric, mode for categorical)
      - Categorical label encoding (fit on train, apply to test)
      - Min-max feature scaling (per-column)
      - Temporal feature extraction from datetime columns
      - Outlier detection and capping (IQR or Z-score method)

    Attributes:
        numeric_cols:     List of numeric column names detected during fit.
        categorical_cols: List of categorical column names detected during fit.
        medians:          Dict of column → median value for imputation.
        modes:            Dict of column → mode value for categorical imputation.
        label_encoders:   Dict of column → {category: int_code}.
        min_vals:         Dict of column → min value for scaling.
        max_vals:         Dict of column → max value for scaling.
        fitted:           Whether fit() has been called.
    """

    # Columns that should be treated as categorical
    KNOWN_CATEGORICAL = {
        "transaction_type", "currency", "status", "channel",
        "risk_level", "nationality", "country", "originating_country",
        "destination_country", "id_type", "source_of_funds",
    }

    # Columns that should never be scaled
    EXCLUDE_FROM_SCALING = {"id", "customer_id", "transaction_id"}

    def __init__(self) -> None:
        """Initialize an unfitted preprocessor."""
        self.numeric_cols: List[str] = []
        self.categorical_cols: List[str] = []
        self.medians: Dict[str, float] = {}
        self.modes: Dict[str, Any] = {}
        self.label_encoders: Dict[str, Dict[str, int]] = {}
        self.min_vals: Dict[str, float] = {}
        self.max_vals: Dict[str, float] = {}
        self.feature_names_out: List[str] = []
        self.fitted: bool = False

    # ---------------------------------------------------------------------------
    # fit
    # ---------------------------------------------------------------------------

    def fit(self, df: DatasetType) -> "AMLDataPreprocessor":
        """
        Fit the preprocessor on training data.

        Computes medians, modes, label encodings, and scaling parameters.

        Args:
            df: List of row dicts (training data).

        Returns:
            self (for chaining)

        Raises:
            ValueError: If df is empty.
        """
        if not df:
            raise ValueError("Cannot fit on empty dataset.")

        all_keys = set()
        for row in df:
            all_keys.update(row.keys())

        numeric_cols = []
        categorical_cols = []

        for key in all_keys:
            values = [row.get(key) for row in df if row.get(key) is not None]
            if not values:
                continue
            if key in self.KNOWN_CATEGORICAL:
                categorical_cols.append(key)
            elif isinstance(values[0], (int, float)):
                numeric_cols.append(key)
            else:
                categorical_cols.append(key)

        self.numeric_cols = sorted(numeric_cols)
        self.categorical_cols = sorted(categorical_cols)

        # Compute medians
        for col in self.numeric_cols:
            vals = [row[col] for row in df if row.get(col) is not None
                    and isinstance(row[col], (int, float))]
            self.medians[col] = statistics.median(vals) if vals else 0.0

        # Compute modes for categoricals
        for col in self.categorical_cols:
            vals = [str(row[col]) for row in df if row.get(col) is not None]
            if vals:
                freq: Dict[str, int] = {}
                for v in vals:
                    freq[v] = freq.get(v, 0) + 1
                self.modes[col] = max(freq, key=freq.get)
            else:
                self.modes[col] = "unknown"

        # Build label encoders
        for col in self.categorical_cols:
            unique_vals = sorted(
                {str(row[col]) for row in df if row.get(col) is not None}
            )
            self.label_encoders[col] = {v: i for i, v in enumerate(unique_vals)}

        # Apply imputation + encoding to compute scaling params
        imputed = self.handle_missing(df)
        encoded = self.encode_categoricals(imputed)

        all_numeric_after = self.numeric_cols + self.categorical_cols
        for col in all_numeric_after:
            if col in self.EXCLUDE_FROM_SCALING:
                continue
            vals = [row.get(col) for row in encoded
                    if row.get(col) is not None and isinstance(row.get(col), (int, float))]
            if vals:
                self.min_vals[col] = min(vals)
                self.max_vals[col] = max(vals)

        # Output feature names (numeric + encoded categorical)
        self.feature_names_out = [
            col for col in self.numeric_cols + self.categorical_cols
            if col not in self.EXCLUDE_FROM_SCALING
        ]

        self.fitted = True
        logger.info(
            "AMLDataPreprocessor fitted: %d numeric, %d categorical, %d total features",
            len(self.numeric_cols), len(self.categorical_cols), len(self.feature_names_out)
        )
        return self

    # ---------------------------------------------------------------------------
    # transform
    # ---------------------------------------------------------------------------

    def transform(self, df: DatasetType) -> List[List[float]]:
        """
        Transform data using fitted parameters.

        Args:
            df: List of row dicts.

        Returns:
            List of feature vectors (each is a List[float]).

        Raises:
            RuntimeError: If preprocessor has not been fitted.
        """
        if not self.fitted:
            raise RuntimeError("Preprocessor must be fitted before transform(). Call fit() first.")

        imputed = self.handle_missing(df)
        encoded = self.encode_categoricals(imputed)
        scaled = self.scale_features(encoded)

        result = []
        for row in scaled:
            vector = [
                float(row.get(col, 0.0) or 0.0)
                for col in self.feature_names_out
            ]
            result.append(vector)

        return result

    # ---------------------------------------------------------------------------
    # fit_transform
    # ---------------------------------------------------------------------------

    def fit_transform(self, df: DatasetType) -> List[List[float]]:
        """
        Fit on data and immediately transform it.

        Args:
            df: Training data as list of row dicts.

        Returns:
            Transformed feature matrix (List of List[float]).
        """
        self.fit(df)
        return self.transform(df)

    # ---------------------------------------------------------------------------
    # handle_missing
    # ---------------------------------------------------------------------------

    def handle_missing(self, df: DatasetType) -> DatasetType:
        """
        Impute missing values in a dataset.

        Numeric columns use median imputation.
        Categorical columns use mode imputation.
        Columns not seen during fit are filled with 0 or 'unknown'.

        Args:
            df: Dataset as list of row dicts.

        Returns:
            New dataset with no None values in known columns.
        """
        result = []
        for row in df:
            new_row = dict(row)
            for col in self.numeric_cols:
                if new_row.get(col) is None:
                    new_row[col] = self.medians.get(col, 0.0)
            for col in self.categorical_cols:
                if new_row.get(col) is None:
                    new_row[col] = self.modes.get(col, "unknown")
            result.append(new_row)
        return result

    # ---------------------------------------------------------------------------
    # encode_categoricals
    # ---------------------------------------------------------------------------

    def encode_categoricals(self, df: DatasetType) -> DatasetType:
        """
        Label-encode categorical columns using fitted encoder mappings.

        Unknown categories encountered during transform are assigned the next
        available integer code (len of known codes).

        Args:
            df: Dataset with imputed values.

        Returns:
            Dataset with categorical columns replaced by integer codes.
        """
        result = []
        for row in df:
            new_row = dict(row)
            for col in self.categorical_cols:
                val = str(new_row.get(col, "unknown"))
                encoder = self.label_encoders.get(col, {})
                if val in encoder:
                    new_row[col] = encoder[val]
                else:
                    new_row[col] = len(encoder)  # unseen category
            result.append(new_row)
        return result

    # ---------------------------------------------------------------------------
    # scale_features
    # ---------------------------------------------------------------------------

    def scale_features(self, df: DatasetType) -> DatasetType:
        """
        Apply min-max scaling to all numeric and encoded categorical features.

        Values outside the training range are clipped to [0, 1].

        Args:
            df: Dataset with encoded values.

        Returns:
            Dataset with scaled feature values in [0, 1].
        """
        result = []
        for row in df:
            new_row = dict(row)
            for col in list(self.min_vals.keys()):
                val = new_row.get(col)
                if val is None or not isinstance(val, (int, float)):
                    new_row[col] = 0.0
                    continue
                mn = self.min_vals[col]
                mx = self.max_vals[col]
                if mx == mn:
                    new_row[col] = 0.0
                else:
                    scaled = (val - mn) / (mx - mn)
                    new_row[col] = max(0.0, min(1.0, scaled))
            result.append(new_row)
        return result

    # ---------------------------------------------------------------------------
    # create_time_features
    # ---------------------------------------------------------------------------

    def create_time_features(self, df: DatasetType, col: str) -> DatasetType:
        """
        Extract temporal features from a datetime column.

        Adds: {col}_hour, {col}_day_of_week, {col}_month, {col}_is_weekend,
              {col}_is_off_hours.

        Args:
            df:  Dataset as list of row dicts.
            col: Name of the datetime column to process.

        Returns:
            Dataset with new temporal feature columns added.
        """
        result = []
        for row in df:
            new_row = dict(row)
            val = row.get(col)
            if val is None:
                new_row[f"{col}_hour"] = 12
                new_row[f"{col}_day_of_week"] = 0
                new_row[f"{col}_month"] = 1
                new_row[f"{col}_is_weekend"] = 0
                new_row[f"{col}_is_off_hours"] = 0
            else:
                if isinstance(val, str):
                    try:
                        val = datetime.fromisoformat(val.replace("Z", "+00:00"))
                    except ValueError:
                        val = datetime.now(timezone.utc)
                hour = val.hour
                dow = val.weekday()
                new_row[f"{col}_hour"] = hour
                new_row[f"{col}_day_of_week"] = dow
                new_row[f"{col}_month"] = val.month
                new_row[f"{col}_is_weekend"] = 1 if dow >= 5 else 0
                new_row[f"{col}_is_off_hours"] = 1 if (hour < 8 or hour >= 20) else 0
            result.append(new_row)
        return result

    # ---------------------------------------------------------------------------
    # detect_outliers
    # ---------------------------------------------------------------------------

    def detect_outliers(
        self,
        df: DatasetType,
        col: str,
        method: str = "iqr",
    ) -> Dict[str, Any]:
        """
        Detect outliers in a numeric column using the specified method.

        Methods:
          - "iqr":    IQR method (Q1 - 1.5*IQR, Q3 + 1.5*IQR)
          - "zscore": Z-score method (|z| > 3.0)

        Args:
            df:     Dataset as list of row dicts.
            col:    Column name to check.
            method: Detection method ('iqr' or 'zscore').

        Returns:
            Dict: {outlier_indices: List[int], outlier_count: int,
                   lower_bound: float, upper_bound: float, method: str}
        """
        vals = [(i, row[col]) for i, row in enumerate(df)
                if row.get(col) is not None and isinstance(row.get(col), (int, float))]

        if not vals:
            return {"outlier_indices": [], "outlier_count": 0,
                    "lower_bound": 0.0, "upper_bound": 0.0, "method": method}

        raw_vals = [v for _, v in vals]

        if method == "iqr":
            sorted_vals = sorted(raw_vals)
            n = len(sorted_vals)
            q1 = sorted_vals[n // 4]
            q3 = sorted_vals[(3 * n) // 4]
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
        elif method == "zscore":
            mean = statistics.mean(raw_vals)
            std = statistics.stdev(raw_vals) if len(raw_vals) > 1 else 1.0
            lower = mean - 3.0 * std
            upper = mean + 3.0 * std
        else:
            raise ValueError(f"Unknown method: {method}. Use 'iqr' or 'zscore'.")

        outlier_indices = [i for i, v in vals if v < lower or v > upper]

        return {
            "outlier_indices": outlier_indices,
            "outlier_count": len(outlier_indices),
            "lower_bound": round(lower, 4),
            "upper_bound": round(upper, 4),
            "method": method,
        }

    # ---------------------------------------------------------------------------
    # get_feature_names
    # ---------------------------------------------------------------------------

    def get_feature_names(self) -> List[str]:
        """
        Return the list of output feature names after transformation.

        Returns:
            List of feature name strings in transform output order.

        Raises:
            RuntimeError: If preprocessor has not been fitted.
        """
        if not self.fitted:
            raise RuntimeError("Must call fit() before get_feature_names().")
        return list(self.feature_names_out)

    # ---------------------------------------------------------------------------
    # save
    # ---------------------------------------------------------------------------

    def save(self, path: str) -> None:
        """
        Persist the fitted preprocessor state to a JSON file.

        Args:
            path: Filesystem path to write the JSON file.

        Raises:
            RuntimeError: If the preprocessor has not been fitted.
        """
        if not self.fitted:
            raise RuntimeError("Cannot save an unfitted preprocessor.")

        state = {
            "numeric_cols": self.numeric_cols,
            "categorical_cols": self.categorical_cols,
            "medians": self.medians,
            "modes": self.modes,
            "label_encoders": self.label_encoders,
            "min_vals": self.min_vals,
            "max_vals": self.max_vals,
            "feature_names_out": self.feature_names_out,
            "fitted": True,
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

        logger.info("AMLDataPreprocessor saved to %s", path)

    # ---------------------------------------------------------------------------
    # load
    # ---------------------------------------------------------------------------

    @classmethod
    def load(cls, path: str) -> "AMLDataPreprocessor":
        """
        Load a previously saved preprocessor state from JSON.

        Args:
            path: Filesystem path to the JSON file.

        Returns:
            A fitted AMLDataPreprocessor instance.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)

        preprocessor = cls()
        preprocessor.numeric_cols = state["numeric_cols"]
        preprocessor.categorical_cols = state["categorical_cols"]
        preprocessor.medians = state["medians"]
        preprocessor.modes = state["modes"]
        preprocessor.label_encoders = state["label_encoders"]
        preprocessor.min_vals = state["min_vals"]
        preprocessor.max_vals = state["max_vals"]
        preprocessor.feature_names_out = state["feature_names_out"]
        preprocessor.fitted = state.get("fitted", True)

        logger.info("AMLDataPreprocessor loaded from %s", path)
        return preprocessor

    def __repr__(self) -> str:
        status = "fitted" if self.fitted else "unfitted"
        return (
            f"AMLDataPreprocessor({status}, "
            f"numeric={len(self.numeric_cols)}, "
            f"categorical={len(self.categorical_cols)})"
        )
