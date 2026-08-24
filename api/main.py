# ruff: noqa: I001
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from api.routers.member import member_router
from api.routers.clinician import clinician_router
from api.routers.user import router as user_router
from api.routers.community import community_router
from api.routers.community.chat import router as chat_router
from api.routers.community.notifications import router as notifications_router
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
    """Load long-lived runtime dependencies before serving requests."""
    # Keep startup loading explicit because model artefacts are deployment assets rather
    # than request-scoped state and should fail fast if they are missing.
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

    print("All models and explainers loaded from disk and ready.")
    yield

app = FastAPI(
    title="Breast Cancer DSS API",
    description="Intelligent Decision Support System for Breast Cancer Risk Assessment",
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(member_router, prefix="/api/member", tags=["Member"])
app.include_router(clinician_router, prefix="/api/clinician", tags=["Clinician"])
app.include_router(user_router, prefix="/api/users", tags=["Users"])
app.include_router(community_router, prefix="/api/community", tags=["Community"])
app.include_router(chat_router, prefix="/api/chat", tags=["Chat"])
app.include_router(notifications_router, prefix="/api", tags=["notifications"])


@app.get("/")
async def root():
    """Return a minimal health response for quick availability checks."""
    return {"message": "Breast Cancer DSS API is running."}
