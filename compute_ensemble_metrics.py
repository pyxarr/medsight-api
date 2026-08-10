from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
import joblib
import numpy as np
from pathlib import Path

from ml.data.wdbc_loader import load_wdbc
from ml.data.ucth_loader import load_ucth
from ml.data.coimbra_loader import load_coimbra
from ml.models.ensemble import BreastCancerEnsemble

SAVED = Path("ml/saved_models")

# Load datasets and get test splits
wisconsin_features, wisconsin_labels, _ = load_wdbc()
ucth_features, ucth_labels, _ = load_ucth()
coimbra_features, coimbra_labels, _ = load_coimbra()

_, ucth_test, _, ucth_test_labels = train_test_split(
    ucth_features, ucth_labels, test_size=0.2, random_state=42, stratify=ucth_labels
)
_, wisconsin_test, _, _ = train_test_split(
    wisconsin_features, wisconsin_labels, test_size=0.2, random_state=42, stratify=wisconsin_labels
)
_, coimbra_test, _, _ = train_test_split(
    coimbra_features, coimbra_labels, test_size=0.2, random_state=42, stratify=coimbra_labels
)

# Load ensemble
ensemble = BreastCancerEnsemble()
ensemble.load()

# Run ensemble on all test rows using UCTH test set as the base
# Match row counts using the minimum test set size
min_rows = min(len(ucth_test), len(wisconsin_test), len(coimbra_test))

predictions = []
probabilities = []
confidence_scores = []
agreement_counts = {"High": 0, "Mixed": 0, "Low": 0, "Single Model": 0}

for i in range(min_rows):
    result = ensemble.predict(
        ucth_features=ucth_test.iloc[[i]],
        wisconsin_features=wisconsin_test.iloc[[i]],
        coimbra_features=coimbra_test.iloc[[i]],
    )
    probabilities.append(result["final_risk_score"])
    predictions.append(1 if result["final_risk_score"] >= 0.5 else 0)
    confidence_scores.append(result["confidence_percent"])
    agreement_counts[result["agreement"]] += 1

true_labels = ucth_test_labels.iloc[:min_rows].values

print("── Ensemble Metrics ────────────────────")
print(f"  Accuracy  : {accuracy_score(true_labels, predictions):.3f}")
print(f"  Precision : {precision_score(true_labels, predictions):.3f}")
print(f"  Recall    : {recall_score(true_labels, predictions):.3f}")
print(f"  F1 Score  : {f1_score(true_labels, predictions):.3f}")
print(f"  ROC-AUC   : {roc_auc_score(true_labels, probabilities):.3f}")
print(f"  Mean Confidence: {np.mean(confidence_scores):.1f}%")
print(f"  Agreement — High: {agreement_counts['High']}, Mixed: {agreement_counts['Mixed']}, Low: {agreement_counts['Low']}")
print("────────────────────────────────────────")