import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_admin
from app.db.models import AuditLog, User
from app.db.session import get_db
from app.schemas.admin import UserAdminResponse, UserListAdminResponse

router = APIRouter(prefix="/v1/admin/users", tags=["admin-users"])


@router.get("", response_model=UserListAdminResponse)
async def list_users(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(User)
    total_r = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_r.scalar_one()
    offset = (page - 1) * per_page
    rows = await db.execute(q.order_by(User.created_at.desc()).offset(offset).limit(per_page))
    users = rows.scalars().all()
    return UserListAdminResponse(
        data=[UserAdminResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("/{user_id}/ban", status_code=200)
async def ban_user(
    user_id: uuid.UUID,
    payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(User).where(User.id == user_id))
    user = r.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    db.add(AuditLog(
        admin_id=uuid.UUID(payload["sub"]),
        action="ban_user",
        target_type="user",
        target_id=str(user_id),
    ))
    await db.commit()
    return {"message": f"User {user_id} banned"}


@router.post("/{user_id}/unban", status_code=200)
async def unban_user(
    user_id: uuid.UUID,
    payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(User).where(User.id == user_id))
    user = r.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = True
    db.add(AuditLog(
        admin_id=uuid.UUID(payload["sub"]),
        action="unban_user",
        target_type="user",
        target_id=str(user_id),
    ))
    await db.commit()
    return {"message": f"User {user_id} unbanned"}
