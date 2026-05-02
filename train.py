from pathlib import Path
import joblib
import pandas as pd

from ml.data.wdbc_loader import load_wdbc
from ml.data.ucth_loader import load_ucth
from ml.data.coimbra_loader import load_coimbra
from ml.models.wisconsin_model import train_wisconsin_model
from ml.models.ucth_model import train_ucth_model
from ml.models.coimbra_model import train_coimbra_model
from ml.inference.shap_explainer import RiskExplainer
from ml.inference.ood_detector import OutOfDistributionDetector

SAVED_MODELS_DIRECTORY = Path("ml/saved_models")

def main():
    print("Starting ML pipeline training and artifact persistence...")

    # 1. Load all 3 datasets
    print("Loading datasets...")
    wisconsin_training_features, wisconsin_training_labels, _ = load_wdbc()
    ucth_training_features, ucth_training_labels, _ = load_ucth()
    coimbra_training_features, coimbra_training_labels, _ = load_coimbra()

    # 2. Train all 3 models (this internally saves the 6 .pkl files)
    print("Training individual models...")
    train_wisconsin_model()
    train_ucth_model()
    train_coimbra_model()
    print("  Individual models trained and saved.")

    # 3. Load the saved preprocessors back from disk
    print("Loading preprocessors from disk...")
    wisconsin_preprocessor = joblib.load(SAVED_MODELS_DIRECTORY / "wisconsin_preprocessor.pkl")
    ucth_preprocessor = joblib.load(SAVED_MODELS_DIRECTORY / "ucth_preprocessor.pkl")
    coimbra_preprocessor = joblib.load(SAVED_MODELS_DIRECTORY / "coimbra_preprocessor.pkl")

    # 4. Transform the full training features using loaded preprocessors
    print("Scaling training features...")
    scaled_wisconsin_training_features = wisconsin_preprocessor.transform(wisconsin_training_features)
    scaled_ucth_training_features = ucth_preprocessor.transform(ucth_training_features)
    scaled_coimbra_training_features = coimbra_preprocessor.transform(coimbra_training_features)

    # Need the models themselves to fit the SHAP explainer
    # We load them from disk to ensure consistency
    wisconsin_model = joblib.load(SAVED_MODELS_DIRECTORY / "wisconsin_model.pkl")
    ucth_model = joblib.load(SAVED_MODELS_DIRECTORY / "ucth_model.pkl")
    coimbra_model = joblib.load(SAVED_MODELS_DIRECTORY / "coimbra_model.pkl")

    # 5. Fit RiskExplainer and save
    print("Fitting RiskExplainer (SHAP)...")
    explainer = RiskExplainer()
    explainer.fit(
        wisconsin_model, scaled_wisconsin_training_features,
        ucth_model,      scaled_ucth_training_features,
        coimbra_model,   scaled_coimbra_training_features,
    )
    explainer.save()
    print("  RiskExplainer saved to disk.")

    # 6. Fit OutOfDistributionDetector on raw UCTH and save
    print("Fitting OutOfDistributionDetector...")
    ood_detector = OutOfDistributionDetector()
    ood_detector.fit(ucth_training_features)
    ood_detector.save()
    print("  OutOfDistributionDetector saved to disk.")

    print("\n✅ All ML artifacts have been trained and persisted successfully.")

if __name__ == "__main__":
    main()
