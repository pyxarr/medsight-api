import pandas as pd


def load_coimbra():
    dataframe = pd.read_csv("data/raw/coimbra_breast_cancer.csv")

    # Rename columns to clean readable names
    # MCP.1 uses a dot in the original — we replace with underscore
    dataframe = dataframe.rename(columns={
        "Age":            "age",
        "BMI":            "body_mass_index",
        "Glucose":        "glucose",
        "Insulin":        "insulin",
        "HOMA":           "homeostasis_model_assessment",
        "Leptin":         "leptin",
        "Adiponectin":    "adiponectin",
        "Resistin":       "resistin",
        "MCP.1":          "monocyte_chemoattractant_protein",
        "Classification": "label",
    })

    # Remap labels to match our convention across all datasets
    # Original: 1=healthy(benign), 2=patient(malignant)
    # Our convention: 0=benign, 1=malignant
    dataframe["label"] = dataframe["label"].map({
        1: 0,
        2: 1,
    })

    feature_columns = [column for column in dataframe.columns if column != "label"]
    features        = dataframe[feature_columns]
    labels          = dataframe["label"]

    metadata = {
        "name":        "Coimbra",
        "n_samples":   len(features),
        "n_malignant": int(labels.sum()),
        "n_benign":    int((labels == 0).sum()),
    }

    return features, labels, metadata