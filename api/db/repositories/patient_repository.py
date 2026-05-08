from datetime import datetime, timezone
from uuid import UUID as PythonUUID

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.patient import Patient


class PatientRepository:
    """Handle patient profile lookup and identifier generation."""

    async def get_by_external_id(
        self,
        database_session: AsyncSession,
        patient_external_id: str,
    ) -> Patient | None:
        """Return one patient by the human-readable patient identifier."""
        patient_query = select(Patient).where(Patient.patient_id == patient_external_id)
        patient_result = await database_session.execute(patient_query)
        return patient_result.scalar_one_or_none()

    async def create_patient(
        self,
        database_session: AsyncSession,
        first_name: str,
        last_name: str,
        patient_external_id: str | None = None,
    ) -> Patient:
        """Create one patient profile and assign an identifier when needed."""
        resolved_patient_external_id = patient_external_id
        if resolved_patient_external_id is None:
            resolved_patient_external_id = await self.generate_next_patient_id(database_session)

        patient_record = Patient(
            patient_id=resolved_patient_external_id,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
        )
        database_session.add(patient_record)
        await database_session.flush()
        await database_session.refresh(patient_record)
        return patient_record

    async def get_or_create_by_external_id(
        self,
        database_session: AsyncSession,
        first_name: str,
        last_name: str,
        patient_external_id: str | None,
    ) -> Patient:
        """Return an existing patient by identifier or create a new profile."""
        if patient_external_id:
            existing_patient = await self.get_by_external_id(
                database_session=database_session,
                patient_external_id=patient_external_id,
            )
            if existing_patient is not None:
                return existing_patient

        return await self.create_patient(
            database_session=database_session,
            first_name=first_name,
            last_name=last_name,
            patient_external_id=patient_external_id,
        )

    async def generate_next_patient_id(self, database_session: AsyncSession) -> str:
        """Generate the next patient identifier in the current-year sequence."""
        current_year = datetime.now(timezone.utc).year
        sequence_query = select(
            func.max(cast(func.split_part(Patient.patient_id, "-", 3), Integer))
        ).where(Patient.patient_id.like(f"P-{current_year}-%"))
        sequence_result = await database_session.execute(sequence_query)
        highest_sequence = sequence_result.scalar_one_or_none() or 0
        next_sequence = highest_sequence + 1

        return f"P-{current_year}-{next_sequence:03d}"

    async def get_by_internal_id(
        self,
        database_session: AsyncSession,
        patient_uuid: PythonUUID,
    ) -> Patient | None:
        """Return one patient by the internal UUID key."""
        patient_query = select(Patient).where(Patient.id == patient_uuid)
        patient_result = await database_session.execute(patient_query)
        return patient_result.scalar_one_or_none()
