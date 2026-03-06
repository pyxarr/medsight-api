import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
)

from ml.data.wdbc_loader import load_wdbc
from ml.preprocessing.wisconsin_preprocessor import build_wisconsin_preprocessor


def train_wisconsin_model():
    """
    Trains a Random Forest on the WDBC dataset.

    Steps:
    1. Load the data
    2. Split into training and test sets (80/20)
    3. Preprocess both sets
    4. Train the Random Forest
    5. Evaluate and print results
    """

    # ── Load ──────────────────────────────────────────────────────────────
    features, labels, metadata = load_wdbc()

    # ── Split ─────────────────────────────────────────────────────────────
    # random_state=42 means the split is reproducible — same split every run
    # stratify=labels means both splits keep the same malignant/benign ratio
    training_features, test_features, training_labels, test_labels = train_test_split(
        features,
        labels,
        test_size=0.2,
        random_state=42,
        stratify=labels,
    )

    # ── Preprocess ────────────────────────────────────────────────────────
    # IMPORTANT: we fit the preprocessor ONLY on training data
    # then apply it to test data — this prevents data leakage
    preprocessor = build_wisconsin_preprocessor()
    scaled_training_features = preprocessor.fit_transform(training_features)
    scaled_test_features      = preprocessor.transform(test_features)

    # ── Train ─────────────────────────────────────────────────────────────
    # n_estimators=100  — number of trees in the forest
    # class_weight      — compensates for the imbalance between
    #                     malignant (212) and benign (357) samples
    model = RandomForestClassifier(
        n_estimators=100,
        class_weight="balanced",
        random_state=42,
    )
    model.fit(scaled_training_features, training_labels)

    # ── Evaluate ──────────────────────────────────────────────────────────
    predictions       = model.predict(scaled_test_features)
    predicted_probabilities = model.predict_proba(scaled_test_features)[:, 1]

    accuracy  = accuracy_score(test_labels, predictions)
    precision = precision_score(test_labels, predictions)
    recall    = recall_score(test_labels, predictions)
    f1        = f1_score(test_labels, predictions)

    print(f"── WDBC Model Results ──────────────────")
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
    train_wisconsin_model()