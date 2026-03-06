import joblib
from pathlib import Path

from ml.models.wisconsin_model import train_wisconsin_model
from ml.models.ucth_model import train_ucth_model
from ml.models.coimbra_model import train_coimbra_model


SAVED_MODELS_DIR = Path("ml/saved_models")
SAVED_MODELS_DIR.mkdir(parents=True, exist_ok=True)

# How much each dataset contributes when all 3 are present.
# When fewer datasets are available the weights are
# recalculated proportionally at prediction time.
DATASET_WEIGHTS = {
    "wisconsin": 0.4,
    "ucth":      0.4,
    "coimbra":   0.2,
}

# Maximum spread between scores to still count as agreement
HIGH_AGREEMENT_THRESHOLD  = 0.2
MIXED_AGREEMENT_THRESHOLD = 0.4


class BreastCancerEnsemble:
    """
    Combines up to 3 individual models into one final prediction.

    Clinical records (UCTH) are always required.
    FNA biopsy (Wisconsin) and blood panel (Coimbra) are optional.

    The more datasets provided, the higher the confidence.
    """

    def __init__(self):
        self.wisconsin_model        = None
        self.wisconsin_preprocessor = None

        self.ucth_model             = None
        self.ucth_preprocessor      = None

        self.coimbra_model          = None
        self.coimbra_preprocessor   = None

        self.is_trained             = False

    def train(self):
        """
        Trains all 3 models and stores them.
        """
        print("Training all 3 models...")
        print("=" * 40)

        self.wisconsin_model, self.wisconsin_preprocessor, wisconsin_scores = train_wisconsin_model()
        self.ucth_model,      self.ucth_preprocessor,      ucth_scores      = train_ucth_model()
        self.coimbra_model,   self.coimbra_preprocessor,   coimbra_scores   = train_coimbra_model()

        self.is_trained = True

        print("=" * 40)
        print("All models trained successfully.")

        return {
            "wisconsin": wisconsin_scores,
            "ucth":      ucth_scores,
            "coimbra":   coimbra_scores,
        }

    def save(self):
        """
        Saves all 3 trained models and their preprocessors to disk.
        This means we only train once — the API loads from disk every time.
        """
        if not self.is_trained:
            raise RuntimeError("Cannot save — ensemble has not been trained yet.")

        joblib.dump(self.wisconsin_model,        SAVED_MODELS_DIR / "wisconsin_model.pkl")
        joblib.dump(self.wisconsin_preprocessor, SAVED_MODELS_DIR / "wisconsin_preprocessor.pkl")

        joblib.dump(self.ucth_model,             SAVED_MODELS_DIR / "ucth_model.pkl")
        joblib.dump(self.ucth_preprocessor,      SAVED_MODELS_DIR / "ucth_preprocessor.pkl")

        joblib.dump(self.coimbra_model,          SAVED_MODELS_DIR / "coimbra_model.pkl")
        joblib.dump(self.coimbra_preprocessor,   SAVED_MODELS_DIR / "coimbra_preprocessor.pkl")

        print("All models saved to ml/saved_models/")

    def load(self):
        """
        Loads all 3 trained models and preprocessors from disk.
        Call this in the API instead of train() so we don't
        retrain every time a request comes in.
        """
        self.wisconsin_model        = joblib.load(SAVED_MODELS_DIR / "wisconsin_model.pkl")
        self.wisconsin_preprocessor = joblib.load(SAVED_MODELS_DIR / "wisconsin_preprocessor.pkl")

        self.ucth_model             = joblib.load(SAVED_MODELS_DIR / "ucth_model.pkl")
        self.ucth_preprocessor      = joblib.load(SAVED_MODELS_DIR / "ucth_preprocessor.pkl")

        self.coimbra_model          = joblib.load(SAVED_MODELS_DIR / "coimbra_model.pkl")
        self.coimbra_preprocessor   = joblib.load(SAVED_MODELS_DIR / "coimbra_preprocessor.pkl")

        self.is_trained = True
        print("All models loaded from ml/saved_models/")

    def predict(
        self,
        ucth_features,           # always required — basic clinical records
        wisconsin_features=None, # optional — FNA biopsy measurements
        coimbra_features=None,   # optional — blood biomarker panel
    ):
        """
        Predicts risk using whichever datasets are provided.

        ucth_features      — always required (pandas DataFrame, one row)
        wisconsin_features — optional (pandas DataFrame, one row)
        coimbra_features   — optional (pandas DataFrame, one row)
        """
        if not self.is_trained:
            raise RuntimeError(
                "Ensemble must be trained before predicting. Call train() first."
            )

        # ── Collect scores from available models ──────────────────────────
        available_scores  = {}
        available_weights = {}

        # UCTH always runs
        scaled_ucth      = self.ucth_preprocessor.transform(ucth_features)
        ucth_probability = float(self.ucth_model.predict_proba(scaled_ucth)[0][1])
        available_scores["ucth"]  = ucth_probability
        available_weights["ucth"] = DATASET_WEIGHTS["ucth"]

        # Wisconsin runs only if FNA data was provided
        if wisconsin_features is not None:
            scaled_wisconsin      = self.wisconsin_preprocessor.transform(wisconsin_features)
            wisconsin_probability = float(
                self.wisconsin_model.predict_proba(scaled_wisconsin)[0][1]
            )
            available_scores["wisconsin"]  = wisconsin_probability
            available_weights["wisconsin"] = DATASET_WEIGHTS["wisconsin"]

        # Coimbra runs only if blood panel data was provided
        if coimbra_features is not None:
            scaled_coimbra      = self.coimbra_preprocessor.transform(coimbra_features)
            coimbra_probability = float(
                self.coimbra_model.predict_proba(scaled_coimbra)[0][1]
            )
            available_scores["coimbra"]  = coimbra_probability
            available_weights["coimbra"] = DATASET_WEIGHTS["coimbra"]

        # ── Recalculate weights proportionally ────────────────────────────
        # If only 2 models ran their weights must still sum to 1.0
        total_weight = sum(available_weights.values())
        normalised_weights = {
            dataset: weight / total_weight
            for dataset, weight in available_weights.items()
        }

        # ── Weighted average → final risk score ───────────────────────────
        final_risk_score = sum(
            normalised_weights[dataset] * score
            for dataset, score in available_scores.items()
        )

        # ── Risk level ────────────────────────────────────────────────────
        if final_risk_score >= 0.7:
            risk_level = "High"
        elif final_risk_score >= 0.3:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        # ── Cross dataset agreement ───────────────────────────────────────
        # Only meaningful when more than one model ran
        if len(available_scores) == 1:
            agreement = "Single Model"
        else:
            all_score_values = list(available_scores.values())
            spread           = max(all_score_values) - min(all_score_values)

            if spread <= HIGH_AGREEMENT_THRESHOLD:
                agreement = "High"
            elif spread <= MIXED_AGREEMENT_THRESHOLD:
                agreement = "Mixed"
            else:
                agreement = "Low"

        # ── Model confidence ──────────────────────────────────────────────
        # Base confidence — how far the score is from 0.5 (uncertain midpoint)
        # 0.9 or 0.1 = very confident | 0.5 = completely uncertain
        distance_from_uncertain = abs(final_risk_score - 0.5)
        base_confidence         = distance_from_uncertain * 2

        # Boost confidence slightly when more models agree
        number_of_models   = len(available_scores)
        confidence_boost   = (number_of_models - 1) * 0.05
        final_confidence   = min(base_confidence + confidence_boost, 1.0)
        confidence_percent = round(final_confidence * 100)

        # ── Clinical guidance ─────────────────────────────────────────────
        clinical_guidance = self._get_clinical_guidance(
            risk_level, agreement, number_of_models
        )

        return {
            "final_risk_score":   round(final_risk_score, 2),
            "risk_level":         risk_level,
            "confidence_percent": confidence_percent,
            "agreement":          agreement,
            "models_used":        number_of_models,
            "individual_scores":  available_scores,
            "clinical_guidance":  clinical_guidance,
        }

    def _get_clinical_guidance(self, risk_level, agreement, number_of_models):
        """
        Returns clinical guidance text based on risk level and agreement.
        Mirrors the guidance shown in the doctor report mockup.
        """
        if risk_level == "High" and agreement == "High":
            return "Priority follow-up recommended. Specialist consultation warranted."
        elif risk_level == "High" and agreement in ("Mixed", "Low"):
            return "Follow-up recommended. Mixed model agreement — clinical correlation important."
        elif risk_level == "High" and agreement == "Single Model":
            return "Follow-up recommended. Provide additional test data to increase confidence."
        elif risk_level == "Medium" and agreement == "High":
            return "Follow-up imaging within 3-6 months recommended."
        elif risk_level == "Medium":
            return "Enhanced monitoring appropriate. Clinical correlation suggested."
        else:
            return "Routine screening schedule. No immediate concerns identified."


if __name__ == "__main__":
    from ml.data.ucth_loader import load_ucth
    from ml.data.wdbc_loader import load_wdbc

    ucth_features,      ucth_labels,      _ = load_ucth()
    wisconsin_features, wisconsin_labels, _ = load_wdbc()

    ensemble = BreastCancerEnsemble()
    ensemble.train()
    ensemble.save()

    print()

    fresh_ensemble = BreastCancerEnsemble()
    fresh_ensemble.load()

    print()
    print("── Test 1: Clinical only (patient form) ──")
    result = fresh_ensemble.predict(
        ucth_features=ucth_features.iloc[[0]],
    )
    print("Risk Score :", result["final_risk_score"])
    print("Risk Level :", result["risk_level"])
    print("Confidence :", result["confidence_percent"], "%")
    print("Agreement  :", result["agreement"])
    print("Guidance   :", result["clinical_guidance"])

    print()
    print("── Test 2: Clinical + FNA (doctor form) ──")
    result = fresh_ensemble.predict(
        ucth_features=ucth_features.iloc[[0]],
        wisconsin_features=wisconsin_features.iloc[[0]],
    )
    print("Risk Score :", result["final_risk_score"])
    print("Risk Level :", result["risk_level"])
    print("Confidence :", result["confidence_percent"], "%")
    print("Agreement  :", result["agreement"])
    print("Guidance   :", result["clinical_guidance"])