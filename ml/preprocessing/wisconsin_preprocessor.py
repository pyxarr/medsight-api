from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer


def build_wisconsin_preprocessor():
    """
    WDBC has 30 continuous features with no missing values.

    We do two things:
    1. SimpleImputer  — fills any missing values with the median of that column
                        (median is safer than mean when there are outliers)
    2. StandardScaler — rescales every feature so it has a mean of 0
                        and a standard deviation of 1
    """
    pipeline = Pipeline(steps=[
        ("fill_missing_values", SimpleImputer(strategy="median")),
        ("scale_features",      StandardScaler()),
    ])

    return pipeline