import logging
from typing import Any
from uuid import UUID as PythonUUID

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.repositories.assessment_repository import create_clinician_assessment
from api.db.repositories.batch_repository import BatchRepository
from api.db.repositories.patient_repository import PatientRepository
from api.db.session import get_db
from api.lib.auth import CurrentUser, require_role
from api.lib.storage import build_batch_storage_path, upload_batch_csv
from api.routers.clinician.inference_service import (
    parse_batch_csv,
    prepare_assessment_dataframes,
    run_inference_and_explain,
    build_assessment_response_payload,
)
from api.schemas.assessment import (
    BiopsyData,
    BloodPanelData,
    ClinicianManualAssessRequest,
    ClinicianPredictionRequest,
    ClinicalData,
)
from api.schemas.assessment_history import (
    BatchAssessmentResponse,
    BatchRowResult,
    BatchSummaryResponse,
)

LOGGER = logging.getLogger(__name__)

router = APIRouter()

REQUIRED_BATCH_COLUMNS = [
    "patient_name",
    "cli_age",
    "cli_menopause",
    "cli_tumor_size_cm",
    "cli_invasive_nodes",
    "cli_breast_side",
    "cli_metastasis",
    "cli_breast_quadrant",
    "cli_breast_disease_history",
]


def _normalise_cell_value(raw_value: Any) -> Any:
    """Return a clean scalar value while treating empty cells as missing."""
    if pd.isna(raw_value):
        return None

    if isinstance(raw_value, str):
        stripped_value = raw_value.strip()
        return stripped_value or None

    return raw_value


def _split_patient_name(patient_name: str) -> tuple[str, str]:
    """Split one patient name into first and last name components."""
    name_parts = [name_part for name_part in patient_name.strip().split() if name_part]
    if not name_parts:
        raise ValueError("Patient name is required for each batch row.")

    if len(name_parts) == 1:
        return name_parts[0], name_parts[0]

    return name_parts[0], " ".join(name_parts[1:])


def _ensure_required_batch_columns(batch_dataframe: pd.DataFrame) -> None:
    """Validate that the uploaded CSV contains all mandatory columns."""
    missing_columns = [
        column_name
        for column_name in REQUIRED_BATCH_COLUMNS
        if column_name not in batch_dataframe.columns
    ]
    if missing_columns:
        raise ValueError(
            "CSV is missing mandatory columns: " + ", ".join(sorted(missing_columns))
        )


def _build_optional_payload(
    row_payload: pd.Series,
    column_names: list[str],
    prefix: str,
) -> dict[str, Any] | None:
    """Return one optional dataset payload or reject partially filled blocks."""
    if not column_names:
        return None

    payload: dict[str, Any] = {}
    filled_columns: list[str] = []
    for column_name in column_names:
        normalised_value = _normalise_cell_value(row_payload[column_name])
        if normalised_value is not None:
            payload[column_name.replace(prefix, "", 1)] = normalised_value
            filled_columns.append(column_name)

    if 0 < len(filled_columns) < len(column_names):
        raise ValueError(
            f"{prefix[:-1].capitalize()} block is incomplete. Fill every {prefix[:-1]} field or leave the block empty."
        )

    if len(filled_columns) == len(column_names):
        return payload

    return None


def _build_clinical_payload(row_payload: pd.Series) -> ClinicalData:
    """Build the validated clinical payload for one batch row."""
    clinical_field_values: dict[str, Any] = {}
    clinical_column_mapping = {
        "age": "cli_age",
        "menopause": "cli_menopause",
        "tumor_size_cm": "cli_tumor_size_cm",
        "invasive_nodes": "cli_invasive_nodes",
        "breast_side": "cli_breast_side",
        "metastasis": "cli_metastasis",
        "breast_quadrant": "cli_breast_quadrant",
        "breast_disease_history": "cli_breast_disease_history",
    }

    for field_name, column_name in clinical_column_mapping.items():
        normalised_value = _normalise_cell_value(row_payload[column_name])
        if normalised_value is None:
            raise ValueError(f"Missing mandatory clinical field: {column_name}.")
        clinical_field_values[field_name] = normalised_value

    return ClinicalData(**clinical_field_values)


def _build_batch_request(
    row_payload: pd.Series,
    batch_dataframe: pd.DataFrame,
    patient_external_id: str,
) -> ClinicianPredictionRequest:
    """Build one clinician prediction request from a CSV row."""
    biopsy_column_names = [
        column_name for column_name in batch_dataframe.columns if column_name.startswith("bio_")
    ]
    blood_column_names = [
        column_name for column_name in batch_dataframe.columns if column_name.startswith("blood_")
    ]

    biopsy_payload = _build_optional_payload(row_payload, biopsy_column_names, "bio_")
    blood_panel_payload = _build_optional_payload(row_payload, blood_column_names, "blood_")

    return ClinicianPredictionRequest(
        patient_id=patient_external_id,
        clinical_data=_build_clinical_payload(row_payload),
        biopsy_data=BiopsyData(**biopsy_payload) if biopsy_payload is not None else None,
        blood_panel=(
            BloodPanelData(**blood_panel_payload)
            if blood_panel_payload is not None
            else None
        ),
    )




async def _run_clinician_assessment_pipeline(
    request: Request,
    body: ClinicianPredictionRequest,
    current_user: CurrentUser,
    database_session: AsyncSession,
    patient_uuid: PythonUUID,
    batch_id: PythonUUID | None = None,
) -> dict[str, Any]:
    """Run inference and persist one clinician assessment."""
    ucth_dataframe, wisconsin_dataframe, coimbra_dataframe = prepare_assessment_dataframes(
        request=request,
        body=body,
    )
    prediction_result, shap_drivers = run_inference_and_explain(
        request=request,
        ucth_dataframe=ucth_dataframe,
        wisconsin_dataframe=wisconsin_dataframe,
        coimbra_dataframe=coimbra_dataframe,
    )
    response_payload = build_assessment_response_payload(
        prediction_result=prediction_result,
        shap_drivers=shap_drivers,
        patient_external_id=body.patient_id,
    )

    try:
        await create_clinician_assessment(
            database_session=database_session,
            clinician_user_id=current_user.id,
            patient_id=patient_uuid,
            patient_external_id=body.patient_id,
            assessment_role="clinician",
            clinical_data=body.clinical_data.model_dump(),
            biopsy_data=(
                body.biopsy_data.model_dump() if body.biopsy_data is not None else None
            ),
            blood_panel_data=(
                body.blood_panel.model_dump() if body.blood_panel is not None else None
            ),
            risk_score=response_payload["risk_score"],
            risk_level=response_payload["risk_level"],
            confidence_percent=response_payload["confidence_percent"],
            agreement=response_payload["agreement"],
            models_used=response_payload["models_used"],
            individual_scores=response_payload["individual_scores"],
            clinical_guidance=response_payload["clinical_guidance"],
            key_risk_drivers=response_payload["key_risk_drivers"],
            ood_warning=response_payload["ood_warning"],
            batch_id=batch_id,
        )
    except Exception:
        LOGGER.exception(
            "Failed to persist clinician assessment for patient_id=%s clinician_user_id=%s",
            body.patient_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Assessment could not be saved. Please try again or contact support "
                "if the problem persists."
            ),
        )

    return response_payload



@router.post("/manual-assess")
async def clinician_manual_assess(
    request: Request,
    body: ClinicianManualAssessRequest,
    current_user: CurrentUser = Depends(require_role("clinician")),
    database_session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return a clinician assessment report from manual entry input."""
    patient_repository = PatientRepository()
    patient_record = await patient_repository.create_patient(
        database_session=database_session,
        first_name=body.first_name,
        last_name=body.last_name,
    )
    request_body = ClinicianPredictionRequest(
        patient_id=patient_record.patient_id,
        clinical_data=body.clinical_data,
        biopsy_data=None,
        blood_panel=body.blood_panel,
    )

    return await _run_clinician_assessment_pipeline(
        request=request,
        body=request_body,
        current_user=current_user,
        database_session=database_session,
        patient_uuid=patient_record.id,
    )



@router.post("/batch-assess", response_model=BatchAssessmentResponse)
async def clinician_batch_assess(
    request: Request,
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_role("clinician")),
    database_session: AsyncSession = Depends(get_db),
) -> BatchAssessmentResponse:
    """Process a clinician batch CSV and persist successful assessments."""
    if file.filename is None or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch upload requires a CSV file.",
        )

    try:
        batch_dataframe, file_bytes = await parse_batch_csv(file)
        _ensure_required_batch_columns(batch_dataframe)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    storage_path = build_batch_storage_path(str(current_user.id), file.filename)
    try:
        stored_file_path = upload_batch_csv(file_bytes=file_bytes, storage_path=storage_path)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    batch_repository = BatchRepository()
    patient_repository = PatientRepository()
    batch_record = await batch_repository.create_batch(
        database_session=database_session,
        clinician_user_id=current_user.id,
        filename=file.filename,
        file_path=stored_file_path,
        total_records=len(batch_dataframe),
    )

    batch_results: list[BatchRowResult] = []
    success_count = 0

    for row_index, row_payload in batch_dataframe.iterrows():
        raw_patient_name = _normalise_cell_value(row_payload.get("patient_name"))
        patient_name = str(raw_patient_name or "")
        raw_patient_external_id = _normalise_cell_value(row_payload.get("patient_id"))
        fallback_patient_id = str(raw_patient_external_id or "")

        try:
            first_name, last_name = _split_patient_name(patient_name)
            patient_record = await patient_repository.get_or_create_by_external_id(
                database_session=database_session,
                first_name=first_name,
                last_name=last_name,
                patient_external_id=(
                    str(raw_patient_external_id) if raw_patient_external_id is not None else None
                ),
            )
            request_body = _build_batch_request(
                row_payload=row_payload,
                batch_dataframe=batch_dataframe,
                patient_external_id=patient_record.patient_id,
            )
            response_payload = await _run_clinician_assessment_pipeline(
                request=request,
                body=request_body,
                current_user=current_user,
                database_session=database_session,
                patient_uuid=patient_record.id,
                batch_id=batch_record.id,
            )
            batch_results.append(
                BatchRowResult(
                    row_index=row_index + 1,
                    patient_id=patient_record.patient_id,
                    patient_name=f"{patient_record.first_name} {patient_record.last_name}",
                    status="success",
                    result=response_payload,
                )
            )
            success_count += 1
        except HTTPException as exc:
            await database_session.rollback()
            batch_results.append(
                BatchRowResult(
                    row_index=row_index + 1,
                    patient_id=fallback_patient_id,
                    patient_name=patient_name,
                    status="failed",
                    error=str(exc.detail),
                )
            )
        except Exception as exc:
            await database_session.rollback()
            batch_results.append(
                BatchRowResult(
                    row_index=row_index + 1,
                    patient_id=fallback_patient_id,
                    patient_name=patient_name,
                    status="failed",
                    error=str(exc),
                )
            )

    return BatchAssessmentResponse(
        batch_id=batch_record.id,
        summary=BatchSummaryResponse(
            total=len(batch_dataframe),
            success=success_count,
            failed=len(batch_dataframe) - success_count,
        ),
        results=batch_results,
    )
