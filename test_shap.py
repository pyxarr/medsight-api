import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ml.data.wdbc_loader import load_wdbc
from ml.data.ucth_loader import load_ucth
from ml.data.coimbra_loader import load_coimbra
from ml.models.wisconsin_model import train_wisconsin_model
from ml.models.ucth_model import train_ucth_model
from ml.models.coimbra_model import train_coimbra_model
from ml.models.ensemble import BreastCancerEnsemble
from ml.inference.shap_explainer import RiskExplainer
from ml.inference.ood_detector import OutOfDistributionDetector

# ── Load all 3 datasets ───────────────────────────────────────────────────────
wisconsin_features, wisconsin_labels, _ = load_wdbc()
ucth_features,      ucth_labels,      _ = load_ucth()
coimbra_features,   coimbra_labels,   _ = load_coimbra()

# ── Train all 3 models ────────────────────────────────────────────────────────
wisconsin_model, wisconsin_preprocessor, _ = train_wisconsin_model()
ucth_model,      ucth_preprocessor,      _ = train_ucth_model()
coimbra_model,   coimbra_preprocessor,   _ = train_coimbra_model()

# ── Train ensemble ────────────────────────────────────────────────────────────
ensemble = BreastCancerEnsemble()
ensemble.train()

# ── Scale training features for SHAP ─────────────────────────────────────────
scaled_wisconsin_training = wisconsin_preprocessor.transform(wisconsin_features)
scaled_ucth_training      = ucth_preprocessor.transform(ucth_features)
scaled_coimbra_training   = coimbra_preprocessor.transform(coimbra_features)

# ── Fit SHAP explainer ────────────────────────────────────────────────────────
explainer = RiskExplainer()
explainer.fit(
    wisconsin_model, scaled_wisconsin_training,
    ucth_model,      scaled_ucth_training,
    coimbra_model,   scaled_coimbra_training,
)

# ── Fit OOD detector on UCTH (always required) ───────────────────────────────
ood_detector = OutOfDistributionDetector()
ood_detector.fit(ucth_features)

# ── Find sample patients at each risk level ───────────────────────────────────
# We scan through UCTH rows to find Low, Medium, High risk examples
print("Scanning for Low / Medium / High risk patients...")
print("=" * 60)

low_risk_index    = None
medium_risk_index = None
high_risk_index   = None

for row_index in range(len(ucth_features)):
    result = ensemble.predict(
        ucth_features=ucth_features.iloc[[row_index]],
    )
    risk = result["risk_level"]

    if risk == "Low"    and low_risk_index    is None:
        low_risk_index    = row_index
    if risk == "Medium" and medium_risk_index is None:
        medium_risk_index = row_index
    if risk == "High"   and high_risk_index   is None:
        high_risk_index   = row_index

    if all([low_risk_index, medium_risk_index, high_risk_index]):
        break

print(f"  Low    risk patient found at row : {low_risk_index}")
print(f"  Medium risk patient found at row : {medium_risk_index}")
print(f"  High   risk patient found at row : {high_risk_index}")


def print_patient_view(risk_level, row_index):
    """
    What a patient sees — simple, no technical details.
    """
    result = ensemble.predict(
        ucth_features=ucth_features.iloc[[row_index]],
    )

    ood_result = ood_detector.detect(ucth_features.iloc[[row_index]])

    print(f"""
┌─────────────────────────────────────────────┐
│  PATIENT VIEW — {risk_level.upper()} RISK                    
├─────────────────────────────────────────────┤
│  Risk Level    : {result['risk_level']}
│  What to do    : {result['clinical_guidance']}""")

    if ood_result["has_warning"]:
        print(f"│  ⚠️  Warning    : Some values were unusual.")
        print(f"│                  Please consult your doctor.")
    else:
        print(f"│  ✅ No unusual values detected.")

    print("└─────────────────────────────────────────────┘")


def print_doctor_view(risk_level, row_index, include_fna=True, include_blood_panel=True):
    """
    What a doctor or researcher sees — full detailed report.
    """
    ucth_row      = ucth_features.iloc[[row_index]]
    wisconsin_row = wisconsin_features.iloc[[row_index]] if include_fna          else None
    coimbra_row   = coimbra_features.iloc[[row_index]]   if include_blood_panel  else None

    # Ensemble prediction
    result = ensemble.predict(
        ucth_features=ucth_row,
        wisconsin_features=wisconsin_row,
        coimbra_features=coimbra_row,
    )

    # Scale features for SHAP
    scaled_ucth = ucth_preprocessor.transform(ucth_row)
    scaled_wisconsin = wisconsin_preprocessor.transform(wisconsin_row) if include_fna         else None
    scaled_coimbra   = coimbra_preprocessor.transform(coimbra_row)     if include_blood_panel else None

    # SHAP drivers
    drivers = explainer.explain(
        preprocessed_ucth_features=scaled_ucth,
        ucth_feature_names=list(ucth_features.columns),
        preprocessed_wisconsin_features=scaled_wisconsin,
        wisconsin_feature_names=list(wisconsin_features.columns) if include_fna else None,
        preprocessed_coimbra_features=scaled_coimbra,
        coimbra_feature_names=list(coimbra_features.columns) if include_blood_panel else None,
    )

    # OOD check
    ood_result = ood_detector.detect(ucth_row)

    # Datasets used
    datasets_used = ["Clinical (UCTH)"]
    if include_fna:
        datasets_used.append("FNA Biopsy (Wisconsin)")
    if include_blood_panel:
        datasets_used.append("Blood Panel (Coimbra)")

    print(f"""
╔══════════════════════════════════════════════════════╗
║  DOCTOR / RESEARCHER VIEW — {risk_level.upper()} RISK
╠══════════════════════════════════════════════════════╣
║  RISK ASSESSMENT SUMMARY
║  Risk Score       : {result['final_risk_score']}
║  Risk Level       : {result['risk_level']}
║  Model Confidence : {result['confidence_percent']}%
║  Models Used      : {result['models_used']}
║  Datasets         : {', '.join(datasets_used)}
╠══════════════════════════════════════════════════════╣
║  CROSS DATASET AGREEMENT : {result['agreement']}
╠══════════════════════════════════════════════════════╣
║  INDIVIDUAL MODEL SCORES""")
    for dataset, score in result["individual_scores"].items():
        print(f"║    {dataset:<12} : {score}")

    print("╠══════════════════════════════════════════════════════╣")
    print("║  KEY RISK DRIVERS (SHAP)")
    for index, driver in enumerate(drivers, 1):
        arrow     = "↑" if driver["direction"] == "increases_risk" else "↓"
        sign      = "+" if driver["direction"] == "increases_risk" else "-"
        print(f"║    #{index} {driver['feature']:<30} {arrow} {sign}{driver['percent']}%")

    print("╠══════════════════════════════════════════════════════╣")
    print("║  OOD WARNING")
    if ood_result["has_warning"]:
        for flag in ood_result["flagged"]:
            print(f"║    ⚠️  {flag['feature']} — {flag['standard_deviations_away']} std away ({flag['severity']})")
    else:
        print("║    ✅ All values within expected range")

    print("╠══════════════════════════════════════════════════════╣")
    print(f"║  CLINICAL GUIDANCE")
    print(f"║    {result['clinical_guidance']}")
    print("╚══════════════════════════════════════════════════════╝")


# ─────────────────────────────────────────────────────────────────────────────
# Run all scenarios
# ─────────────────────────────────────────────────────────────────────────────

for risk_level, row_index in [
    ("Low",    low_risk_index),
    ("Medium", medium_risk_index),
    ("High",   high_risk_index),
]:
    if row_index is None:
        print(f"\n⚠️  No {risk_level} risk patient found in dataset")
        continue

    print(f"\n{'#' * 60}")
    print(f"#  SCENARIO: {risk_level.upper()} RISK PATIENT")
    print(f"{'#' * 60}")

    # Patient view — clinical only
    print_patient_view(risk_level, row_index)

    # Doctor view — clinical only
    print_doctor_view(risk_level, row_index,
                      include_fna=False, include_blood_panel=False)

    # Doctor view — clinical + FNA
    print_doctor_view(risk_level, row_index,
                      include_fna=True, include_blood_panel=False)

    # Doctor view — all 3 datasets
    print_doctor_view(risk_level, row_index,
                      include_fna=True, include_blood_panel=True)
