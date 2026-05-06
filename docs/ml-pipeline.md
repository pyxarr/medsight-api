## MedSight API Machine Learning Pipeline

## 1. Overview

The machine learning layer in `medsight-api` is built around three independent supervised classification models trained on three different breast cancer datasets. Each dataset has a different feature space and a different clinical modality, so the pipeline does not attempt to force them into one unified training table. Instead, the backend trains one model per dataset, then combines their probabilities through a weighted ensemble.

The three modalities are:

- biopsy / fine needle aspiration measurements from the Wisconsin dataset
- clinical record features from the UCTH dataset
- blood biomarker values from the Coimbra dataset

This structure matches the real-world input behaviour of the product. Clinical data is always available and forms the minimum inference path. Biopsy and blood data are additional evidence sources that improve the richness of the final assessment when they exist.

## 2. Pipeline Goals

The pipeline is designed to satisfy five constraints at once:

1. work with small and medium-sized tabular datasets
2. keep each dataset in its original feature space
3. generate probability outputs rather than hard labels only
4. support model explainability through SHAP
5. allow warnings when a patient's clinical values fall outside the training distribution

## 3. Dataset Inventory

| Dataset | Source | Samples | Features | Modality | Label Convention |
| --- | --- | --- | --- | --- | --- |
| `WDBC` | `sklearn.datasets.load_breast_cancer()` | `569` | `30` | Fine needle aspiration biopsy | sklearn uses `0 = malignant`, `1 = benign`; loader flips to `1 = malignant`, `0 = benign` |
| `UCTH` | Local CSV at `data/raw/ucth_breast_cancer.csv` | `213` | `8` | Clinical records | loader maps `Malignant = 1`, `Benign = 0` |
| `Coimbra` | Local CSV at `data/raw/coimbra_breast_cancer.csv` | `116` | `9` | Blood biomarkers | loader maps `1 = healthy` to `0`, and `2 = patient` to `1` |

## 4. Dataset Loading Layer

Dataset loading lives in:

```text
ml/data/
```

Each dataset has its own loader and remains isolated from the others.

### 4.1 Wisconsin Loader

File:

```text
ml/data/wdbc_loader.py
```

Behaviour:

- loads the built-in sklearn breast cancer dataset
- converts feature matrix into a pandas DataFrame using sklearn feature names
- flips labels from sklearn's convention to the project convention
- returns `features`, `labels`, and `metadata`

Returned metadata includes:

- dataset name
- sample count
- malignant count
- benign count

### 4.2 UCTH Loader

File:

```text
ml/data/ucth_loader.py
```

Behaviour:

- reads `data/raw/ucth_breast_cancer.csv`
- treats `#` as missing values with `na_values=["#"]`
- drops non-predictive columns `S/N` and `Year`
- renames columns to clean programmatic names
- strips whitespace from `breast_quadrant`
- maps categorical text into numeric codes
- converts string-coded numeric flags into numeric values
- fills remaining missing values with the column mode
- maps labels to `1 = malignant`, `0 = benign`
- returns `features`, `labels`, and `metadata`

Final UCTH feature columns:

```text
age
menopause
tumor_size_cm
invasive_nodes
breast_side
metastasis
breast_quadrant
breast_disease_history
```

### 4.3 Coimbra Loader

File:

```text
ml/data/coimbra_loader.py
```

Behaviour:

- reads `data/raw/coimbra_breast_cancer.csv`
- renames columns into readable snake_case names
- replaces `MCP.1` with `monocyte_chemoattractant_protein`
- remaps labels into the project convention
- returns `features`, `labels`, and `metadata`

Final Coimbra feature columns:

```text
age
body_mass_index
glucose
insulin
homeostasis_model_assessment
leptin
adiponectin
resistin
monocyte_chemoattractant_protein
```

### 4.4 Aggregate Loader

File:

```text
ml/data/data_loader.py
```

This helper calls all three dataset loaders, prints a summary, and returns a dictionary keyed by dataset name. It is a convenience utility and not the primary training entry point.

## 5. Preprocessing Layer

Preprocessing logic lives in:

```text
ml/preprocessing/
```

Each dataset has a dedicated preprocessor because the feature types and distribution behaviour differ.

### 5.1 Wisconsin Preprocessor

File:

```text
ml/preprocessing/wisconsin_preprocessor.py
```

Builder function:

```python
build_wisconsin_preprocessor()
```

Pipeline steps:

1. `SimpleImputer(strategy="median")`
2. `StandardScaler()`

Why this is appropriate:

- all 30 features are continuous biopsy measurements
- the median is robust to outliers
- scaling helps tree explanations and keeps transformed feature spaces consistent across tooling

### 5.2 UCTH Preprocessor

File:

```text
ml/preprocessing/ucth_preprocessor.py
```

Builder function:

```python
build_ucth_preprocessor()
```

The UCTH preprocessor uses a `ColumnTransformer` with two branches.

Numeric columns:

```text
age
tumor_size_cm
invasive_nodes
```

Numeric steps:

1. `SimpleImputer(strategy="median")`
2. `StandardScaler()`

Categorical columns:

```text
menopause
breast_side
metastasis
breast_quadrant
breast_disease_history
```

Categorical steps:

1. `SimpleImputer(strategy="most_frequent")`

Why categorical values are not scaled:

- they are already encoded as meaningful discrete values
- scaling `0/1` category flags would turn simple categories into continuous distances
- keeping them discrete preserves the original semantics of the clinical record encoding

### 5.3 Coimbra Preprocessor

File:

```text
ml/preprocessing/coimbra_preprocessor.py
```

Builder function:

```python
build_coimbra_preprocessor()
```

Pipeline steps:

1. `SimpleImputer(strategy="median")`
2. `FunctionTransformer(np.log1p)`
3. `StandardScaler()`

Why `log1p` is used:

- several biomarkers are right-skewed
- large extreme values can distort model training
- `log1p` compresses high values while handling zero safely

## 6. Model Training Layer

Training logic lives in:

```text
ml/models/
```

Each dataset has its own trainer function and evaluation output.

### 6.1 Shared Training Pattern

All three model trainers follow the same structure:

1. load dataset
2. split into train and test sets with `test_size=0.2`
3. use `random_state=42` for reproducibility
4. use `stratify=labels` to preserve class balance
5. fit the dataset-specific preprocessor on training data only
6. transform training and test data
7. train a `RandomForestClassifier`
8. evaluate with accuracy, precision, recall, and F1
9. return `model`, `preprocessor`, and score dictionary

The classifier configuration used in all three trainers is:

```python
RandomForestClassifier(
    n_estimators=100,
    class_weight="balanced",
    random_state=42,
)
```

### 6.2 Why Random Forest Was Chosen

Random Forest is a good fit for this repository because:

- the datasets are relatively small
- the features are tabular rather than image-based
- probability outputs are available through `predict_proba()`
- class imbalance is handled through `class_weight="balanced"`
- the model family works directly with SHAP `TreeExplainer`
- the training pipeline remains readable and operationally lightweight

### 6.3 Model Metrics

The current documented metrics produced by training are:

| Model | Accuracy | Precision | Recall | F1 |
| --- | --- | --- | --- | --- |
| `Wisconsin` | `0.974` | `1.000` | `0.929` | `0.963` |
| `UCTH` | `0.884` | `0.889` | `0.842` | `0.865` |
| `Coimbra` | `0.708` | `0.800` | `0.615` | `0.696` |

These values reflect the current evaluation outputs documented elsewhere in the repository. They are not hard-coded into the training functions, but they describe the current expected performance profile.

## 7. Ensemble Layer

Ensemble logic lives in:

```text
ml/models/ensemble.py
```

Class:

```python
BreastCancerEnsemble
```

### 7.1 Responsibility

The ensemble is responsible for:

- loading trained models and preprocessors from disk
- deciding which model paths can run for a request
- transforming incoming DataFrames with the correct preprocessor
- extracting malignant probabilities from each model
- normalising weights when fewer than three datasets are present
- producing one final risk score and interpretation bundle

### 7.2 Dataset Requirements

- `ucth_features` are always required
- `wisconsin_features` are optional
- `coimbra_features` are optional

This means the minimum supported prediction path is clinical input only.

### 7.3 Fixed Weights

The ensemble defines:

```python
DATASET_WEIGHTS = {
    "wisconsin": 0.4,
    "ucth": 0.4,
    "coimbra": 0.2,
}
```

### 7.4 Dynamic Weight Normalisation

If fewer than three model paths are present, the ensemble recalculates weights proportionally so they still sum to `1.0`.

Example:

- if UCTH and Wisconsin are present, their effective weights become `0.5` and `0.5`
- if only UCTH is present, its effective weight becomes `1.0`

### 7.5 Final Risk Score

The final risk score is the weighted average of the available malignant probabilities.

Returned key:

```text
final_risk_score
```

The score is rounded to two decimal places in the response bundle.

### 7.6 Risk Levels

Thresholds implemented in code:

```text
High   >= 0.7
Medium >= 0.3
Low    < 0.3
```

### 7.7 Agreement Levels

The ensemble calculates agreement from the spread between model scores.

Threshold constants:

```python
HIGH_AGREEMENT_THRESHOLD = 0.2
MIXED_AGREEMENT_THRESHOLD = 0.4
```

Result mapping:

- one model only: `Single Model`
- spread `<= 0.2`: `High`
- spread `<= 0.4`: `Mixed`
- spread `> 0.4`: `Low`

### 7.8 Confidence Calculation

Confidence is based on distance from the uncertain midpoint plus a small boost for additional contributing models.

Code logic:

```text
distance_from_uncertain = abs(final_risk_score - 0.5)
base_confidence = distance_from_uncertain * 2
confidence_boost = (number_of_models - 1) * 0.05
final_confidence = min(base_confidence + confidence_boost, 1.0)
confidence_percent = round(final_confidence * 100)
```

### 7.9 Clinical Guidance Output

The ensemble maps `risk_level`, `agreement`, and `number_of_models` into a guidance string through the private helper:

```python
_get_clinical_guidance(...)
```

This guidance is reused by both member and clinician responses, although the member route exposes it in a simplified context.

## 8. Explainability Layer

Explainability logic lives in:

```text
ml/inference/shap_explainer.py
```

Class:

```python
RiskExplainer
```

### 8.1 Responsibility

The explainer provides feature-level attribution for whichever model paths were available during clinician inference.

### 8.2 Fitting Strategy

During training, the explainer is fitted with:

- Wisconsin model + transformed Wisconsin training features
- UCTH model + transformed UCTH training features
- Coimbra model + transformed Coimbra training features

For each model, it builds a SHAP explainer using:

```python
shap.TreeExplainer(
    model,
    data=shap.maskers.Independent(training_features, max_samples=100),
)
```

### 8.3 Why `TreeExplainer`

`TreeExplainer` is appropriate because all trained models are Random Forest classifiers. It is faster and more exact for tree-based models than generic SHAP explainers.

### 8.4 Inference-Time Behaviour

The explainer receives already-preprocessed features. It does not run the preprocessors itself.

Expected SHAP output indexing pattern:

```python
shap_values[0, :, 1]
```

Interpretation:

- first dimension: one patient row
- second dimension: one value per feature
- third dimension: class index, where `1` is the malignant class

### 8.5 Returned Driver Format

For each top driver, the explainer returns:

- `feature`
- `dataset`
- `contribution`
- `direction`
- `percent`

Drivers are sorted by absolute SHAP contribution and truncated to the requested top count. The default is:

```python
top_number_of_drivers=4
```

### 8.6 Persisted Artefact

Saved path:

```text
ml/saved_models/shap_explainer.pkl
```

## 9. Out-of-Distribution Detection Layer

Out-of-distribution logic lives in:

```text
ml/inference/ood_detector.py
```

Class:

```python
OutOfDistributionDetector
```

### 9.1 Responsibility

The detector checks whether an incoming patient's clinical feature values are unusually far from the UCTH training distribution.

### 9.2 Fitting Strategy

The detector is fitted on raw UCTH training features, not scaled features. For each feature, it stores:

- training mean
- training standard deviation
- feature name order

### 9.3 Detection Logic

At inference time, for each available clinical feature:

1. compute the absolute distance from the training mean
2. divide by the stored standard deviation
3. compare the result against the threshold

Default threshold in code:

```python
standard_deviation_threshold=3.5
```

Severity rules:

- `Minor` when value is more than `3.5` but not more than `5` standard deviations away
- `Major` when value is more than `5` standard deviations away

### 9.4 Scope

The detector only runs on UCTH clinical features.

It does not run on:

- Wisconsin biopsy features
- Coimbra blood-panel features

### 9.5 Returned Structure

The detector returns:

```json
{
  "has_warning": true,
  "flagged": [
    {
      "feature": "tumor_size_cm",
      "patient_value": 9.2,
      "standard_deviations_away": 4.18,
      "severity": "Minor"
    }
  ]
}
```

### 9.6 Persisted Artefact

Saved path:

```text
ml/saved_models/ood_detector.pkl
```

## 10. Training Entry Point

The canonical training entry point is:

```text
train.py
```

### 10.1 Exact Training Sequence

The script performs these steps in order:

1. load all three datasets
2. train all three models
3. load the saved preprocessors back from disk
4. transform the full training features using the loaded preprocessors
5. load the saved models from disk
6. fit `RiskExplainer`
7. save `RiskExplainer`
8. fit `OutOfDistributionDetector` on raw UCTH features
9. save `OutOfDistributionDetector`

This approach ensures that the downstream explainer and detector are fitted against the same persisted artefacts the API will later load.

### 10.2 Saved Artefacts Produced

Running `python train.py` is expected to result in:

```text
wisconsin_model.pkl
wisconsin_preprocessor.pkl
ucth_model.pkl
ucth_preprocessor.pkl
coimbra_model.pkl
coimbra_preprocessor.pkl
shap_explainer.pkl
ood_detector.pkl
```

## 11. Startup Loading Path

Application startup occurs in:

```text
api/main.py
```

Lifespan startup loads:

1. the persisted ensemble through `BreastCancerEnsemble.load()`
2. the persisted `RiskExplainer`
3. the persisted `OutOfDistributionDetector`
4. the three preprocessors through `joblib.load()`
5. the three datasets again for feature-name ordering only

These objects are stored in `app.state` and then reused for all requests.

## 12. Request-to-Inference Flow

### 12.1 Member Flow

1. member submits `ClinicalData`
2. route builds `ucth_dataframe`
3. detector checks the UCTH clinical values
4. ensemble runs the UCTH model path only
5. route returns simplified risk output

### 12.2 Clinician Flow

1. clinician submits `ClinicalData`
2. route optionally receives `BiopsyData`
3. route optionally receives `BloodPanelData`
4. clinical data becomes `ucth_dataframe`
5. biopsy data becomes `wisconsin_dataframe`
6. blood data becomes `coimbra_dataframe` with injected age
7. detector checks UCTH clinical values
8. ensemble runs all available model paths
9. preprocessors transform available inputs for SHAP
10. `RiskExplainer.explain()` returns top drivers
11. route returns the detailed clinician report

## 13. Verification Scripts

### `test_shap.py`

This script is a local machine learning verification script that exercises:

- dataset loading
- model training
- ensemble predictions across multiple risk scenarios
- SHAP explanation generation
- out-of-distribution warnings

It is useful for quick manual inspection of end-to-end machine learning behaviour.

### `test_api.py`

This script exists for API testing but is currently behind the live implementation. It exercises the current `/api/member/assess` and `/api/clinician/assess` routes across five scenarios.

## 14. Known Implementation Boundaries

- models are static after training and are not retrained in production
- the pipeline is tabular only; there is no imaging model
- no database interaction occurs inside the machine learning layer
- no asynchronous training or background job system exists
- no batch upload endpoint exists yet, even though the machine learning design supports future multi-input use cases
