import uuid
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.messaging import publish_classification_task
from app.core.security import get_current_user_id
from app.core.storage import get_presigned_url, upload_photo
from app.db.models import Result, Submission
from app.db.session import get_db
from app.schemas.submissions import (
    ResultResponse,
    SubmissionCreate,
    SubmissionListResponse,
    SubmissionResponse,
)

router = APIRouter(prefix="/v1/submissions", tags=["submissions"])


async def _enrich(sub: Submission, db: AsyncSession) -> SubmissionResponse:
    photo_url = None
    try:
        photo_url = await get_presigned_url(sub.photo_key)
    except Exception:
        pass

    result_obj: Result | None = None
    if sub.status == "classified":
        r = await db.execute(select(Result).where(Result.submission_id == sub.id))
        result_obj = r.scalar_one_or_none()

    return SubmissionResponse(
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
        result=ResultResponse.model_validate(result_obj) if result_obj else None,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
    )


@router.post("", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
async def create_submission(
    name: str = Form(...),
    age: int = Form(...),
    place_of_living: str = Form(...),
    gender: str = Form(...),
    country_of_origin: str = Form(...),
    description: Optional[str] = Form(default=None),
    photo: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    # Validate form fields via Pydantic model
    body = SubmissionCreate(
        name=name,
        age=age,
        place_of_living=place_of_living,
        gender=gender,
        country_of_origin=country_of_origin,
        description=description,
    )

    # Size guard
    raw = await photo.read()
    if len(raw) > settings.max_photo_size_bytes:
        raise HTTPException(status_code=413, detail="Photo exceeds 10 MB limit")

    try:
        key = await upload_photo(raw, photo.content_type or "image/jpeg", user_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    sub = Submission(
        user_id=uuid.UUID(user_id),
        name=body.name,
        age=body.age,
        place_of_living=body.place_of_living,
        gender=body.gender,
        country_of_origin=body.country_of_origin,
        description=body.description,
        photo_key=key,
        status="pending",
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)

    # Publish async classification task — fire and forget
    try:
        await publish_classification_task(str(sub.id), key)
    except Exception:
        pass  # classification will be retried; submission is already stored

    return await _enrich(sub, db)


@router.get("", response_model=SubmissionListResponse)
async def list_submissions(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * per_page
    base_q = select(Submission).where(
        Submission.user_id == uuid.UUID(user_id),
        Submission.deleted_at.is_(None),
    )
    total_r = await db.execute(select(func.count()).select_from(base_q.subquery()))
    total = total_r.scalar_one()

    rows = await db.execute(
        base_q.order_by(Submission.created_at.desc()).offset(offset).limit(per_page)
    )
    subs = rows.scalars().all()
    items = [await _enrich(s, db) for s in subs]
    return SubmissionListResponse(data=items, total=total, page=page, per_page=per_page)


@router.get("/{submission_id}", response_model=SubmissionResponse)
async def get_submission(
    submission_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Submission).where(
            Submission.id == submission_id,
            Submission.user_id == uuid.UUID(user_id),
            Submission.deleted_at.is_(None),
        )
    )
    sub = r.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    return await _enrich(sub, db)
