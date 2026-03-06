from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import FunctionTransformer
import numpy as np


def build_coimbra_preprocessor():
    """
    Coimbra has 9 continuous blood biomarker features.

    Some features like insulin, leptin and resistin are heavily
    right-skewed — a small number of patients have very high values
    which can confuse the model. We fix this with a log transform.

    We do three things:
    1. SimpleImputer      — fills any missing values with the median
    2. FunctionTransformer — applies log(x + 1) to reduce skewness
                             we use x+1 to avoid log(0) errors
    3. StandardScaler     — rescales everything to mean 0, std 1
    """
    pipeline = Pipeline(steps=[
        ("fill_missing_values",  SimpleImputer(strategy="median")),
        ("reduce_skewness",      FunctionTransformer(np.log1p)),
        ("scale_features",       StandardScaler()),
    ])

    return pipeline