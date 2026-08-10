from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
import joblib
from pathlib import Path

from ml.data.wdbc_loader import load_wdbc
from ml.data.ucth_loader import load_ucth
from ml.data.coimbra_loader import load_coimbra

SAVED = Path("ml/saved_models")

datasets = {
    "WDBC":    (load_wdbc,    "wisconsin"),
    "UCTH":    (load_ucth,    "ucth"),
    "Coimbra": (load_coimbra, "coimbra"),
}

for name, (loader, key) in datasets.items():
    features, labels, _ = loader()
    _, test_features, _, test_labels = train_test_split(
        features, labels, test_size=0.2, random_state=42, stratify=labels
    )
    preprocessor = joblib.load(SAVED / f"{key}_preprocessor.pkl")
    model        = joblib.load(SAVED / f"{key}_model.pkl")
    scaled       = preprocessor.transform(test_features)
    proba        = model.predict_proba(scaled)[:, 1]
    auc          = roc_auc_score(test_labels, proba)
    print(f"{name}: ROC-AUC = {auc:.3f}")