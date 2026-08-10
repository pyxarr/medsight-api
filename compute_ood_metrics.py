from sklearn.model_selection import train_test_split
import joblib
from pathlib import Path
from collections import Counter

from ml.data.ucth_loader import load_ucth
from ml.inference.ood_detector import OutOfDistributionDetector

SAVED = Path("ml/saved_models")

ucth_features, ucth_labels, _ = load_ucth()

_, test_features, _, _ = train_test_split(
    ucth_features, ucth_labels, test_size=0.2, random_state=42, stratify=ucth_labels
)

ood_detector = joblib.load(SAVED / "ood_detector.pkl")

flagged_total = 0
severity_counts = Counter()
feature_counts = Counter()

for i in range(len(test_features)):
    result = ood_detector.detect(test_features.iloc[[i]])
    if result["has_warning"]:
        flagged_total += 1
        for flag in result["flagged"]:
            severity_counts[flag["severity"]] += 1
            feature_counts[flag["feature"]] += 1

total = len(test_features)
print("── OOD Detection Results ───────────────")
print(f"  Total test samples : {total}")
print(f"  Flagged samples    : {flagged_total} ({flagged_total/total*100:.1f}%)")
print(f"  Minor warnings     : {severity_counts['Minor']}")
print(f"  Major warnings     : {severity_counts['Major']}")
print(f"  Most flagged features:")
for feature, count in feature_counts.most_common():
    print(f"    {feature}: {count}")
print("────────────────────────────────────────")