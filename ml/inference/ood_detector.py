import pandas as pd
from pathlib import Path
import joblib


class OutOfDistributionDetector:
    """
    Detects when a patient's feature values fall outside
    the range the model was trained on.

    During training  — we call fit() to learn the average
                       and spread of each feature

    During inference — we call detect() to flag any feature
                       that is more than 3 standard deviations
                       away from the training average
    """

    def __init__(self, standard_deviation_threshold=3.5):
        """
        standard_deviation_threshold — how many standard deviations
        away from the mean before we flag a feature as suspicious.
        3.0 is the standard choice in statistics (covers 99.7% of normal data)
        """
        self.standard_deviation_threshold = standard_deviation_threshold
        self.training_means               = {}
        self.training_standard_deviations = {}
        self.feature_names                = []

    SAVED_MODELS_DIRECTORY = Path(__file__).parent.parent / "saved_models"

    def save(self):
        """
        Saves the fitted OOD detector instance to disk.
        """
        joblib.dump(self, self.SAVED_MODELS_DIRECTORY / "ood_detector.pkl")

    @classmethod
    def load(cls):
        """
        Loads a saved OOD detector instance from disk.
        """
        return joblib.load(cls.SAVED_MODELS_DIRECTORY / "ood_detector.pkl")

    def fit(self, features: pd.DataFrame):
        """
        Learn the average and spread of each feature
        from the training data.
        """
        self.feature_names = list(features.columns)

        for column in self.feature_names:
            self.training_means[column]               = float(features[column].mean())
            self.training_standard_deviations[column] = float(features[column].std())

        return self

    def detect(self, patient_features: pd.DataFrame) -> dict:
        """
        Check a single patient's features against the training distribution.

        Returns a dictionary with:
          has_warning — True if any feature is out of distribution
          flagged     — list of flagged features with details
        """
        flagged_features = []

        for column in self.feature_names:
            if column not in patient_features.columns:
                continue

            patient_value  = float(patient_features[column].iloc[0])
            training_mean  = self.training_means[column]
            training_std   = self.training_standard_deviations[column]

            # Avoid division by zero for constant features
            if training_std == 0:
                continue

            how_many_std_away = abs(patient_value - training_mean) / training_std

            if how_many_std_away > self.standard_deviation_threshold:
                severity = "Major" if how_many_std_away > 5 else "Minor"
                flagged_features.append({
                    "feature":                  column,
                    "patient_value":            round(patient_value, 4),
                    "standard_deviations_away": round(how_many_std_away, 2),
                    "severity":                 severity,
                })

        return {
            "has_warning": len(flagged_features) > 0,
            "flagged":     sorted(
                               flagged_features,
                               key=lambda item: -item["standard_deviations_away"]
                           ),
        }