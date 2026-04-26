import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_admin
from app.db.models import AuditLog, Result, Submission
from app.db.session import get_db
from app.schemas.admin import (
    ResultSummary,
    SubmissionAdminResponse,
    SubmissionListAdminResponse,
)
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/v1/admin/submissions", tags=["admin-submissions"])


async def _photo_url(photo_key: str) -> Optional[str]:
    try:
        from app.config import settings

        endpoint = settings.minio_public_endpoint or settings.minio_endpoint
        scheme = "https" if settings.minio_secure else "http"

        if settings.minio_bucket_public:
            return f"{scheme}://{endpoint}/{settings.minio_bucket}/{photo_key}"

        from miniopy_async import Minio
        from datetime import timedelta

        endpoint = settings.minio_public_endpoint or settings.minio_endpoint
        client = Minio(
            endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        return await client.presigned_get_object(
            settings.minio_bucket, photo_key, expires=timedelta(seconds=3600)
        )
    except Exception as exc:
        logger.warning(
            "failed to build presigned photo url",
            photo_key=photo_key,
            minio_bucket=settings.minio_bucket,
            error=str(exc),
        )
        return None


async def _enrich(sub: Submission, db: AsyncSession) -> SubmissionAdminResponse:
    photo_url = await _photo_url(sub.photo_key)
    result_obj = None
    r = await db.execute(select(Result).where(Result.submission_id == sub.id))
    row = r.scalar_one_or_none()
    if row:
        result_obj = ResultSummary.model_validate(row)

    return SubmissionAdminResponse(
        id=sub.id,
        user_id=sub.user_id,
        name=sub.name,
        age=sub.age,
        place_of_living=sub.place_of_living,
        gender=sub.gender,
        country_of_origin=sub.country_of_origin,
        description=sub.description,
        photo_url=photo_url,
        status=sub.status,
        result=result_obj,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
        deleted_at=sub.deleted_at,
    )


@router.get("", response_model=SubmissionListAdminResponse)
async def list_submissions(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    age_min: Optional[int] = Query(default=None),
    age_max: Optional[int] = Query(default=None),
    gender: Optional[str] = Query(default=None),
    place_of_living: Optional[str] = Query(default=None),
    country_of_origin: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    created_after: Optional[datetime] = Query(default=None),
    created_before: Optional[datetime] = Query(default=None),
    include_deleted: bool = Query(default=False),
    payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(Submission)
    if not include_deleted:
        q = q.where(Submission.deleted_at.is_(None))
    if age_min is not None:
        q = q.where(Submission.age >= age_min)
    if age_max is not None:
        q = q.where(Submission.age <= age_max)
    if gender:
        q = q.where(Submission.gender == gender)
    if place_of_living:
        q = q.where(Submission.place_of_living.ilike(f"%{place_of_living}%"))
    if country_of_origin:
        q = q.where(Submission.country_of_origin == country_of_origin.upper())
    if status:
        q = q.where(Submission.status == status)
    if created_after:
        q = q.where(Submission.created_at >= created_after)
    if created_before:
        q = q.where(Submission.created_at <= created_before)

    total_r = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_r.scalar_one()

    offset = (page - 1) * per_page
    rows = await db.execute(
        q.order_by(Submission.created_at.desc()).offset(offset).limit(per_page)
    )
    subs = rows.scalars().all()
    items = [await _enrich(s, db) for s in subs]
    return SubmissionListAdminResponse(
        data=items, total=total, page=page, per_page=per_page
    )


@router.get("/{submission_id}", response_model=SubmissionAdminResponse)
async def get_submission(
    submission_id: uuid.UUID,
    payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Submission).where(Submission.id == submission_id))
    sub = r.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    return await _enrich(sub, db)


@router.delete("/{submission_id}", status_code=204)
async def delete_submission(
    submission_id: uuid.UUID,
    payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Submission).where(Submission.id == submission_id))
    sub = r.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    sub.deleted_at = datetime.utcnow()
    db.add(
        AuditLog(
            admin_id=uuid.UUID(payload["sub"]),
            action="delete_submission",
            target_type="submission",
            target_id=str(submission_id),
        )
    )
    await db.commit()
