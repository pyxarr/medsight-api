import shap
from pathlib import Path
import joblib


class RiskExplainer:
    """
    Uses SHAP (SHapley Additive exPlanations) to explain
    why the model gave a particular risk score.

    SHAP works by measuring how much each feature pushed
    the prediction higher or lower compared to the average.

    For example:
      Worst Perimeter = 135.1  pushed risk UP   by +35%
      Symmetry        = 0.26   pushed risk DOWN by  -8%

    This powers the Key Risk Drivers section in the doctor report.
    """

    def __init__(self):
        self.wisconsin_explainer = None
        self.ucth_explainer      = None
        self.coimbra_explainer   = None

    SAVED_MODELS_DIRECTORY = Path(__file__).parent.parent / "saved_models"

    def save(self):
        """
        Saves the fitted SHAP explainer instance to disk.
        """
        joblib.dump(self, self.SAVED_MODELS_DIRECTORY / "shap_explainer.pkl")

    @classmethod
    def load(cls):
        """
        Loads a saved SHAP explainer instance from disk.
        """
        return joblib.load(cls.SAVED_MODELS_DIRECTORY / "shap_explainer.pkl")

    def fit(
        self,
        wisconsin_model,           wisconsin_training_features,
        ucth_model,                ucth_training_features,
        coimbra_model,             coimbra_training_features,
    ):
        """
        Creates a SHAP explainer for each model using the training data.
        Only creates an explainer if the model and its data are provided.

        We use TreeExplainer because Random Forest is a tree based model.
        It is fast and exact for tree models.

        We pass a summary of the training data (not all of it) to keep
        things efficient — shap.maskers.Independent handles this.
        """
        print("Fitting SHAP explainers...")

        if ucth_model is not None and ucth_training_features is not None:
            self.ucth_explainer = shap.TreeExplainer(
                ucth_model,
                data=shap.maskers.Independent(ucth_training_features, max_samples=100),
            )
            print("  UCTH explainer ready.")

        if wisconsin_model is not None and wisconsin_training_features is not None:
            self.wisconsin_explainer = shap.TreeExplainer(
                wisconsin_model,
                data=shap.maskers.Independent(wisconsin_training_features, max_samples=100),
            )
            print("  Wisconsin explainer ready.")

        if coimbra_model is not None and coimbra_training_features is not None:
            self.coimbra_explainer = shap.TreeExplainer(
                coimbra_model,
                data=shap.maskers.Independent(coimbra_training_features, max_samples=100),
            )
            print("  Coimbra explainer ready.")

        print("SHAP explainers fitted.")

    def explain(
        self,
        preprocessed_ucth_features,
        ucth_feature_names,
        preprocessed_wisconsin_features=None,
        wisconsin_feature_names=None,
        preprocessed_coimbra_features=None,
        coimbra_feature_names=None,
        top_number_of_drivers=4,
    ):
        """
        Explains the prediction for one patient.

        Takes preprocessed (scaled) features — the same ones
        passed to the model — and returns the top risk drivers.

        SHAP returns an array of shape (1, number_of_features, 2)
          dimension 0 — the patient (just one)
          dimension 1 — one value per feature
          dimension 2 — two classes: index 0 = benign, index 1 = malignant

        We use [0, :, 1] to get all feature values for the malignant class.

        Returns a list of the most influential features sorted
        by how much they changed the risk score.
        """
        all_contributions = []

        # ── UCTH contributions ────────────────────────────────────────────
        if self.ucth_explainer is not None:
            ucth_shap_values = self.ucth_explainer.shap_values(
                preprocessed_ucth_features
            )
            ucth_contributions = self._extract_contributions(
                shap_values=ucth_shap_values[0, :, 1],
                feature_names=ucth_feature_names,
                dataset_name="clinical",
            )
            all_contributions.extend(ucth_contributions)

        # ── Wisconsin contributions ───────────────────────────────────────
        if self.wisconsin_explainer is not None and preprocessed_wisconsin_features is not None:
            wisconsin_shap_values = self.wisconsin_explainer.shap_values(
                preprocessed_wisconsin_features
            )
            wisconsin_contributions = self._extract_contributions(
                shap_values=wisconsin_shap_values[0, :, 1],
                feature_names=wisconsin_feature_names,
                dataset_name="biopsy",
            )
            all_contributions.extend(wisconsin_contributions)

        # ── Coimbra contributions ─────────────────────────────────────────
        if self.coimbra_explainer is not None and preprocessed_coimbra_features is not None:
            coimbra_shap_values = self.coimbra_explainer.shap_values(
                preprocessed_coimbra_features
            )
            coimbra_contributions = self._extract_contributions(
                shap_values=coimbra_shap_values[0, :, 1],
                feature_names=coimbra_feature_names,
                dataset_name="blood_panel",
            )
            all_contributions.extend(coimbra_contributions)

        # ── Sort by absolute contribution and return top drivers ──────────
        all_contributions.sort(
            key=lambda item: abs(item["contribution"]),
            reverse=True
        )
        top_drivers = all_contributions[:top_number_of_drivers]

        # Convert raw SHAP values to readable percentages
        for driver in top_drivers:
            contribution_percent = round(driver["contribution"] * 100)
            driver["direction"]  = "increases_risk" if contribution_percent > 0 else "decreases_risk"
            driver["percent"]    = abs(contribution_percent)

        return top_drivers

    def _extract_contributions(self, shap_values, feature_names, dataset_name):
        """
        Pairs each feature name with its SHAP value
        and tags it with which dataset it came from.
        """
        contributions = []
        for feature_name, shap_value in zip(feature_names, shap_values):
            contributions.append({
                "feature":      feature_name,
                "dataset":      dataset_name,
                "contribution": float(shap_value),
            })
        return contributions