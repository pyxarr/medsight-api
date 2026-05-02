from fastapi import FastAPI
from api.routers import predict
from contextlib import asynccontextmanager
from pathlib import Path
import joblib

from ml.models.ensemble import BreastCancerEnsemble
from ml.inference.shap_explainer import RiskExplainer
from ml.inference.ood_detector import OutOfDistributionDetector
from ml.data.wdbc_loader import load_wdbc
from ml.data.ucth_loader import load_ucth
from ml.data.coimbra_loader import load_coimbra

SAVED_MODELS_DIRECTORY = Path("ml/saved_models")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load everything from disk on startup
    print("Loading ML artifacts from disk...")
    
    # 1. Load ensemble
    app.state.ensemble = BreastCancerEnsemble()
    app.state.ensemble.load()

    # 2. Load SHAP explainer
    app.state.explainer = RiskExplainer.load()

    # 3. Load OOD detector
    app.state.ood_detector = OutOfDistributionDetector.load()

    # 4. Load preprocessors
    app.state.wisconsin_preprocessor = joblib.load(SAVED_MODELS_DIRECTORY / "wisconsin_preprocessor.pkl")
    app.state.ucth_preprocessor      = joblib.load(SAVED_MODELS_DIRECTORY / "ucth_preprocessor.pkl")
    app.state.coimbra_preprocessor   = joblib.load(SAVED_MODELS_DIRECTORY / "coimbra_preprocessor.pkl")

    # 5. Load datasets for feature names only
    wisconsin_features, _, _ = load_wdbc()
    ucth_features,      _, _ = load_ucth()
    coimbra_features,   _, _ = load_coimbra()

    app.state.wisconsin_feature_names = list(wisconsin_features.columns)
    app.state.ucth_feature_names      = list(ucth_features.columns)
    app.state.coimbra_feature_names   = list(coimbra_features.columns)

    print("✅ All models and explainers loaded from disk and ready.")
    yield

app = FastAPI(
    title="Breast Cancer DSS API",
    description="Intelligent Decision Support System for Breast Cancer Risk Assessment",
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(predict.router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "Breast Cancer DSS API is running."}
