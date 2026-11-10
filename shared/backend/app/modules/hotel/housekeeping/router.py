"""FastAPI Router for Housekeeping & Cleaning Operations."""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.modules.hotel.hospitality.models import HotelHousekeepingTask, HotelRoom
from .schemas import HousekeepingTaskCreate, TaskCompleteRequest

router = APIRouter(prefix="/hospitality/housekeeping", tags=["HOT-Housekeeping"])


@router.get("")
@router.get("/tasks")
async def list_tasks(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(HotelHousekeepingTask).where(HotelHousekeepingTask.tenant_id == user.tenant_id)
    if status:
        query = query.where(HotelHousekeepingTask.status == status)
    if priority:
        query = query.where(HotelHousekeepingTask.priority == priority)
    query = query.order_by(HotelHousekeepingTask.created_at.desc())
    res = await db.execute(query)
    return res.scalars().all()


@router.post("")
@router.post("/tasks")
async def create_task(
    data: HousekeepingTaskCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = HotelHousekeepingTask(
        tenant_id=user.tenant_id,
        room_number=data.room_number,
        task_type=data.task_type,
        priority=data.priority,
        assigned_to=data.assigned_to,
        notes=data.notes or "",
        status="pending",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.post("/tasks/{task_id}/complete")
async def complete_task(
    task_id: str,
    data: TaskCompleteRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(HotelHousekeepingTask).where(
            HotelHousekeepingTask.id == task_id, HotelHousekeepingTask.tenant_id == user.tenant_id
        )
    )
    task = res.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = "completed"
    task.completed_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    if data.notes:
        task.notes = f"{task.notes} | تم الإنجاز: {data.notes}"

    # Also automatically transition the room status to vacant_clean
    room_query = select(HotelRoom).where(
        HotelRoom.room_number == task.room_number, HotelRoom.tenant_id == user.tenant_id
    )
    room = (await db.execute(room_query)).scalar_one_or_none()
    if room and room.status == "vacant_dirty":
        room.status = "vacant_clean"

    await db.commit()
    await db.refresh(task)
    return {"status": "completed", "task": task}
