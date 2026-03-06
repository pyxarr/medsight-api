import requests

BASE_URL = "http://127.0.0.1:8000/api"


def print_result(title, response):
    print(f"\n{'#' * 60}")
    print(f"#  {title}")
    print(f"{'#' * 60}")
    print(f"Status Code : {response.status_code}")
    import json
    print(json.dumps(response.json(), indent=2))


# ─────────────────────────────────────────────────────────────────────────────
# Test 1 — Patient assess — Low risk
# ─────────────────────────────────────────────────────────────────────────────
response = requests.post(f"{BASE_URL}/patient/assess", json={
    "patient_id": "P-2024-0001",
    "clinical_data": {
        "age":                    25,
        "menopause":              0,
        "tumor_size_cm":          1.0,
        "invasive_nodes":         0,
        "breast_side":            0,
        "metastasis":             0,
        "breast_quadrant":        0,
        "breast_disease_history": 0,
    }
})
print_result("PATIENT VIEW — LOW RISK", response)


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 — Patient assess — High risk
# ─────────────────────────────────────────────────────────────────────────────
response = requests.post(f"{BASE_URL}/patient/assess", json={
    "patient_id": "P-2024-0002",
    "clinical_data": {
        "age":                    62,
        "menopause":              1,
        "tumor_size_cm":          5.5,
        "invasive_nodes":         3,
        "breast_side":            1,
        "metastasis":             1,
        "breast_quadrant":        0,
        "breast_disease_history": 1,
    }
})
print_result("PATIENT VIEW — HIGH RISK", response)


# ─────────────────────────────────────────────────────────────────────────────
# Test 3 — Doctor assess — Clinical only
# ─────────────────────────────────────────────────────────────────────────────
response = requests.post(f"{BASE_URL}/doctor/assess", json={
    "patient_id": "P-2024-0003",
    "clinical_data": {
        "age":                    45,
        "menopause":              1,
        "tumor_size_cm":          3.0,
        "invasive_nodes":         1,
        "breast_side":            0,
        "metastasis":             0,
        "breast_quadrant":        1,
        "breast_disease_history": 0,
    }
})
print_result("DOCTOR VIEW — CLINICAL ONLY", response)


# ─────────────────────────────────────────────────────────────────────────────
# Test 4 — Doctor assess — Clinical + FNA biopsy
# ─────────────────────────────────────────────────────────────────────────────
response = requests.post(f"{BASE_URL}/doctor/assess", json={
    "patient_id": "P-2024-0004",
    "clinical_data": {
        "age":                    55,
        "menopause":              1,
        "tumor_size_cm":          4.0,
        "invasive_nodes":         2,
        "breast_side":            1,
        "metastasis":             1,
        "breast_quadrant":        0,
        "breast_disease_history": 1,
    },
    "biopsy_data": {
        "mean_radius":             20.57,
        "mean_texture":            17.77,
        "mean_perimeter":          132.9,
        "mean_area":               1326.0,
        "mean_smoothness":         0.08474,
        "mean_compactness":        0.07864,
        "mean_concavity":          0.0869,
        "mean_concave_points":     0.07017,
        "mean_symmetry":           0.1812,
        "mean_fractal_dimension":  0.05667,
        "radius_error":            0.5435,
        "texture_error":           0.7339,
        "perimeter_error":         3.398,
        "area_error":              74.08,
        "smoothness_error":        0.005225,
        "compactness_error":       0.01308,
        "concavity_error":         0.01860,
        "concave_points_error":    0.01340,
        "symmetry_error":          0.01389,
        "fractal_dimension_error": 0.003532,
        "worst_radius":            24.99,
        "worst_texture":           23.41,
        "worst_perimeter":         158.8,
        "worst_area":              1956.0,
        "worst_smoothness":        0.1238,
        "worst_compactness":       0.1866,
        "worst_concavity":         0.2416,
        "worst_concave_points":    0.1860,
        "worst_symmetry":          0.2750,
        "worst_fractal_dimension": 0.08902,
    }
})
print_result("DOCTOR VIEW — CLINICAL + FNA BIOPSY", response)


# ─────────────────────────────────────────────────────────────────────────────
# Test 5 — Doctor assess — All 3 datasets
# ─────────────────────────────────────────────────────────────────────────────
response = requests.post(f"{BASE_URL}/doctor/assess", json={
    "patient_id": "P-2024-0005",
    "clinical_data": {
        "age":                    58,
        "menopause":              1,
        "tumor_size_cm":          4.5,
        "invasive_nodes":         2,
        "breast_side":            1,
        "metastasis":             1,
        "breast_quadrant":        0,
        "breast_disease_history": 1,
    },
    "biopsy_data": {
        "mean_radius":             20.57,
        "mean_texture":            17.77,
        "mean_perimeter":          132.9,
        "mean_area":               1326.0,
        "mean_smoothness":         0.08474,
        "mean_compactness":        0.07864,
        "mean_concavity":          0.0869,
        "mean_concave_points":     0.07017,
        "mean_symmetry":           0.1812,
        "mean_fractal_dimension":  0.05667,
        "radius_error":            0.5435,
        "texture_error":           0.7339,
        "perimeter_error":         3.398,
        "area_error":              74.08,
        "smoothness_error":        0.005225,
        "compactness_error":       0.01308,
        "concavity_error":         0.01860,
        "concave_points_error":    0.01340,
        "symmetry_error":          0.01389,
        "fractal_dimension_error": 0.003532,
        "worst_radius":            24.99,
        "worst_texture":           23.41,
        "worst_perimeter":         158.8,
        "worst_area":              1956.0,
        "worst_smoothness":        0.1238,
        "worst_compactness":       0.1866,
        "worst_concavity":         0.2416,
        "worst_concave_points":    0.1860,
        "worst_symmetry":          0.2750,
        "worst_fractal_dimension": 0.08902,
    },
    "blood_panel": {
        "age":                                    58,
        "body_mass_index":                        27.5,
        "glucose":                                102.0,
        "insulin":                                8.5,
        "homeostasis_model_assessment":           2.1,
        "leptin":                                 25.0,
        "adiponectin":                            8.0,
        "resistin":                               12.0,
        "monocyte_chemoattractant_protein":       450.0,
    }
})
print_result("DOCTOR VIEW — ALL 3 DATASETS", response)