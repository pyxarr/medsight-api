from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.compose import ColumnTransformer


UCTH_NUMERIC_COLUMNS     = ["age", "tumor_size_cm", "invasive_nodes"]
UCTH_CATEGORICAL_COLUMNS = ["menopause", "breast_side", "metastasis",
                             "breast_quadrant", "breast_disease_history"]


def build_ucth_preprocessor():
    """
    UCTH has two types of features:

    Numeric columns     — age, tumor size, invasive nodes
                          These get median imputation + scaling

    Categorical columns — menopause, breast side, metastasis, etc.
                          Already encoded as numbers in the loader.
                          These only need missing values filled.
                          We do NOT scale them because they are
                          already meaningful discrete values (0 or 1)
    """
    numeric_pipeline = Pipeline(steps=[
        ("fill_missing_values", SimpleImputer(strategy="median")),
        ("scale_features",      StandardScaler()),
    ])

    categorical_pipeline = Pipeline(steps=[
        ("fill_missing_values", SimpleImputer(strategy="most_frequent")),
    ])

    preprocessor = ColumnTransformer(transformers=[
        ("numeric",     numeric_pipeline,     UCTH_NUMERIC_COLUMNS),
        ("categorical", categorical_pipeline, UCTH_CATEGORICAL_COLUMNS),
    ])

    return preprocessor