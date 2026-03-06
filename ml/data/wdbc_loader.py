import pandas as pd
from sklearn.datasets import load_breast_cancer


def load_wdbc():
    raw = load_breast_cancer()

    X = pd.DataFrame(raw.data, columns=raw.feature_names)

    # sklearn uses 0=malignant, 1=benign
    # we flip it to: 1=malignant, 0=benign (clinical convention)
    y = pd.Series(1 - raw.target, name="label")

    metadata = {
        "name": "WDBC",
        "n_samples": len(X),
        "n_malignant": int(y.sum()),
        "n_benign": int((y == 0).sum()),
    }

    return X, y, metadata