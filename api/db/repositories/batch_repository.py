from uuid import UUID as PythonUUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.assessment import Assessment
from api.models.batch import Batch


class BatchRepository:
    """Handle persistence and retrieval for clinician batch sessions."""

    async def create_batch(
        self,
        database_session: AsyncSession,
        clinician_user_id: PythonUUID,
        filename: str,
        file_path: str,
        total_records: int,
    ) -> Batch:
        """Create one batch session record."""
        batch_record = Batch(
            clinician_id=clinician_user_id,
            filename=filename,
            file_path=file_path,
            total_records=total_records,
        )
        database_session.add(batch_record)

        try:
            await database_session.commit()
        except Exception:
            await database_session.rollback()
            raise

        await database_session.refresh(batch_record)
        return batch_record

    async def list_batches(
        self,
        database_session: AsyncSession,
        clinician_user_id: PythonUUID,
    ) -> list[Batch]:
        """Return batch sessions created by one clinician."""
        batches_query = (
            select(Batch)
            .where(Batch.clinician_id == clinician_user_id)
            .order_by(Batch.created_at.desc())
        )
        batches_result = await database_session.execute(batches_query)
        return list(batches_result.scalars().all())

    async def get_batch(
        self,
        database_session: AsyncSession,
        clinician_user_id: PythonUUID,
        batch_id: PythonUUID,
    ) -> Batch | None:
        """Return one clinician batch by identifier."""
        batch_query = select(Batch).where(
            Batch.id == batch_id,
            Batch.clinician_id == clinician_user_id,
        )
        batch_result = await database_session.execute(batch_query)
        return batch_result.scalar_one_or_none()

    async def count_batch_assessments(
        self,
        database_session: AsyncSession,
        batch_id: PythonUUID,
    ) -> int:
        """Return the number of active assessments attached to one batch."""
        count_query = select(func.count()).select_from(Assessment).where(
            Assessment.batch_id == batch_id,
            Assessment.deleted_at.is_(None),
        )
        count_result = await database_session.execute(count_query)
        return count_result.scalar_one()
