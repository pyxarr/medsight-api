from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
)

from ml.data.coimbra_loader import load_coimbra
from ml.preprocessing.coimbra_preprocessor import build_coimbra_preprocessor


def train_coimbra_model():
    """
    Trains a Random Forest on the Coimbra blood biomarker dataset.

    Coimbra is the smallest dataset (116 samples) and uses
    blood test features instead of cell measurements.
    The preprocessor applies a log transform first to
    handle the skewed biomarker distributions.
    """

    # ── Load ──────────────────────────────────────────────────────────────
    features, labels, metadata = load_coimbra()

    # ── Split ─────────────────────────────────────────────────────────────
    training_features, test_features, training_labels, test_labels = train_test_split(
        features,
        labels,
        test_size=0.2,
        random_state=42,
        stratify=labels,
    )

    # ── Preprocess ────────────────────────────────────────────────────────
    preprocessor = build_coimbra_preprocessor()
    scaled_training_features = preprocessor.fit_transform(training_features)
    scaled_test_features      = preprocessor.transform(test_features)

    # ── Train ─────────────────────────────────────────────────────────────
    model = RandomForestClassifier(
        n_estimators=100,
        class_weight="balanced",
        random_state=42,
    )
    model.fit(scaled_training_features, training_labels)

    # ── Evaluate ──────────────────────────────────────────────────────────
    predictions = model.predict(scaled_test_features)

    accuracy  = accuracy_score(test_labels, predictions)
    precision = precision_score(test_labels, predictions)
    recall    = recall_score(test_labels, predictions)
    f1        = f1_score(test_labels, predictions)

    print(f"── Coimbra Model Results ───────────────")
    print(f"  Accuracy  : {accuracy:.3f}  (overall correct predictions)")
    print(f"  Precision : {precision:.3f}  (of predicted malignant, how many were right)")
    print(f"  Recall    : {recall:.3f}  (of actual malignant, how many did we catch)")
    print(f"  F1 Score  : {f1:.3f}  (balance between precision and recall)")
    print(f"────────────────────────────────────────")

    return model, preprocessor, {
        "accuracy":  round(accuracy, 3),
        "precision": round(precision, 3),
        "recall":    round(recall, 3),
        "f1":        round(f1, 3),
    }


if __name__ == "__main__":
    train_coimbra_model()