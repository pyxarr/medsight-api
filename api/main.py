from fastapi import FastAPI
from api.routers import predict

app = FastAPI(
    title="Breast Cancer DSS API",
    description="Intelligent Decision Support System for Breast Cancer Risk Assessment",
    version="0.1.0",
)

# ── Load models once when the API starts ──────────────────────────────────────
# We use a startup event so models are loaded into memory once
# and reused for every request — not reloaded on every call
@app.on_event("startup")
async def load_models():
    from ml.models.ensemble import BreastCancerEnsemble
    from ml.inference.shap_explainer import RiskExplainer
    from ml.inference.ood_detector import OutOfDistributionDetector
    from ml.data.wdbc_loader import load_wdbc
    from ml.data.ucth_loader import load_ucth
    from ml.data.coimbra_loader import load_coimbra
    from ml.models.wisconsin_model import train_wisconsin_model
    from ml.models.ucth_model import train_ucth_model
    from ml.models.coimbra_model import train_coimbra_model

    # Load ensemble from saved models
    app.state.ensemble = BreastCancerEnsemble()
    app.state.ensemble.load()

    # Load all 3 datasets for SHAP and OOD
    wisconsin_features, _, _ = load_wdbc()
    ucth_features,      _, _ = load_ucth()
    coimbra_features,   _, _ = load_coimbra()

    # Retrain preprocessors on full data for SHAP
    wisconsin_model, wisconsin_preprocessor, _ = train_wisconsin_model()
    ucth_model,      ucth_preprocessor,      _ = train_ucth_model()
    coimbra_model,   coimbra_preprocessor,   _ = train_coimbra_model()

    scaled_wisconsin = wisconsin_preprocessor.transform(wisconsin_features)
    scaled_ucth      = ucth_preprocessor.transform(ucth_features)
    scaled_coimbra   = coimbra_preprocessor.transform(coimbra_features)

    # Fit SHAP explainer
    app.state.explainer = RiskExplainer()
    app.state.explainer.fit(
        wisconsin_model, scaled_wisconsin,
        ucth_model,      scaled_ucth,
        coimbra_model,   scaled_coimbra,
    )

    # Fit OOD detector on UCTH
    app.state.ood_detector = OutOfDistributionDetector()
    app.state.ood_detector.fit(ucth_features)

    # Store preprocessors for use in predict router
    app.state.wisconsin_preprocessor = wisconsin_preprocessor
    app.state.ucth_preprocessor      = ucth_preprocessor
    app.state.coimbra_preprocessor   = coimbra_preprocessor

    # Store feature names for SHAP
    app.state.wisconsin_feature_names = list(wisconsin_features.columns)
    app.state.ucth_feature_names      = list(ucth_features.columns)
    app.state.coimbra_feature_names   = list(coimbra_features.columns)

    print("✅ All models and explainers loaded and ready.")


app.include_router(predict.router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "Breast Cancer DSS API is running."}