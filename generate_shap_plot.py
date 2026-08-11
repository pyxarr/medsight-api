import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import joblib
import numpy as np
from pathlib import Path

from ml.data.ucth_loader import load_ucth
from ml.inference.shap_explainer import RiskExplainer

SAVED = Path("ml/saved_models")

features, labels, _ = load_ucth()

malignant_samples = features[labels == 1]
sample = malignant_samples.iloc[[0]]

ucth_preprocessor = joblib.load(SAVED / "ucth_preprocessor.pkl")
scaled_sample = ucth_preprocessor.transform(sample)

explainer = RiskExplainer.load()

drivers = explainer.explain(
    preprocessed_ucth_features=scaled_sample,
    ucth_feature_names=list(features.columns),
    top_number_of_drivers=8,
)

# Map internal snake_case feature names to readable clinical labels
feature_labels = {
    "tumor_size_cm":          "Tumour Size (cm)",
    "metastasis":             "Metastasis",
    "menopause":              "Menopause Status",
    "age":                    "Age",
    "breast_quadrant":        "Breast Quadrant",
    "breast_side":            "Breast Side",
    "invasive_nodes":         "Invasive Nodes",
    "breast_disease_history": "Breast Disease History",
}

feature_names  = [feature_labels.get(d["feature"], d["feature"]) for d in drivers]
contributions  = [d["contribution"] if d["direction"] == "increases_risk" else -abs(d["contribution"]) for d in drivers]
colours        = ["#d9534f" if d["direction"] == "increases_risk" else "#5bc0de" for d in drivers]
patient_values = [sample[d["feature"]].values[0] for d in drivers]

# Increase left margin so feature name labels have room and don't collide with bar annotations
fig, ax = plt.subplots(figsize=(12, 6))
fig.subplots_adjust(left=0.22)

bars = ax.barh(feature_names[::-1], contributions[::-1], color=colours[::-1], edgecolor="white", height=0.6)

for bar, val, contrib in zip(bars, patient_values[::-1], contributions[::-1]):
    # Push blue bar labels further left to prevent overlap with the feature name
    if contrib >= 0:
        x_pos = contrib + 0.003
        ha = "left"
    else:
        # Blue bars are small — place label on the right side of zero for clarity
        x_pos = 0.003
        ha = "left"
    ax.text(x_pos, bar.get_y() + bar.get_height() / 2,
            f"value = {val}", va="center", ha=ha, fontsize=9, color="#333333")

ax.axvline(0, color="black", linewidth=0.8)
ax.axvline(0.5, color="grey", linewidth=0.8, linestyle="--", alpha=0.5)
ax.text(0.502, len(drivers) - 0.5, "Model baseline (0.5)", fontsize=8, color="grey")

red_patch  = mpatches.Patch(color="#d9534f", label="Increases malignant risk")
blue_patch = mpatches.Patch(color="#5bc0de", label="Decreases malignant risk")
ax.legend(handles=[red_patch, blue_patch], loc="lower right", fontsize=9)

ax.set_xlabel("SHAP Contribution", fontsize=11)
ax.set_title("SHAP Feature Contributions — High-Risk Patient (UCTH Clinical Pathway)", fontsize=12, pad=12)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

plt.tight_layout()
plt.savefig("shap_plot.png", dpi=300)
print("Saved to shap_plot.png")