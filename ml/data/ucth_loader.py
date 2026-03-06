import pandas as pd


def load_ucth():
    dataframe = pd.read_csv(
        "data/raw/ucth_breast_cancer.csv",
        na_values=["#"]   # treat # as missing
    )

    # Drop columns that are not useful for prediction
    dataframe = dataframe.drop(columns=["S/N", "Year"])

    # Rename columns to clean readable names
    dataframe = dataframe.rename(columns={
        "Age":              "age",
        "Menopause":        "menopause",
        "Tumor Size (cm)":  "tumor_size_cm",
        "Inv-Nodes":        "invasive_nodes",
        "Breast":           "breast_side",
        "Metastasis":       "metastasis",
        "Breast Quadrant":  "breast_quadrant",
        "History":          "breast_disease_history",
        "Diagnosis Result": "label",
    })

    # Strip whitespace from breast_quadrant values
    # (dataset has 'Upper outer ' with trailing space)
    dataframe["breast_quadrant"] = dataframe["breast_quadrant"].str.strip()

    # Encode breast_side text to numbers: Right=1, Left=0
    dataframe["breast_side"] = dataframe["breast_side"].map({
        "Right": 1,
        "Left":  0,
    })

    # Encode breast_quadrant text to numbers
    dataframe["breast_quadrant"] = dataframe["breast_quadrant"].map({
        "Upper outer": 0,
        "Upper inner": 1,
        "Lower outer": 2,
        "Lower inner": 3,
    })

    # These columns came in as strings '0' and '1' — convert to real numbers
    dataframe["metastasis"]             = pd.to_numeric(dataframe["metastasis"], errors="coerce")
    dataframe["breast_disease_history"] = pd.to_numeric(dataframe["breast_disease_history"], errors="coerce")

    # Fill missing values with the most common value in each column
    for column in dataframe.columns:
        if dataframe[column].isnull().sum() > 0:
            most_common_value = dataframe[column].mode()[0]
            dataframe[column] = dataframe[column].fillna(most_common_value)

    # Encode label: Malignant=1, Benign=0
    dataframe["label"] = dataframe["label"].map({
        "Malignant": 1,
        "Benign":    0,
    })

    feature_columns = [column for column in dataframe.columns if column != "label"]
    features        = dataframe[feature_columns]
    labels          = dataframe["label"]

    metadata = {
        "name":        "UCTH",
        "n_samples":   len(features),
        "n_malignant": int(labels.sum()),
        "n_benign":    int((labels == 0).sum()),
    }

    return features, labels, metadata