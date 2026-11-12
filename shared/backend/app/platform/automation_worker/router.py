"""API Router for Background Automation & Cron Worker."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_current_user, require_superadmin
from app.platform.auth.models.user import User
from app.platform.automation_worker.models import AutomationJobLog
from app.platform.automation_worker.runner import JOB_REGISTRY, run_all_jobs, run_job

router = APIRouter(prefix="/modules/automation", tags=["automation-worker"])


class ScheduleToggleSchema(BaseModel):
    is_enabled: bool


@router.get("/jobs")
async def list_automation_jobs(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List all registered automation worker jobs with their schedules and last run status."""
    output = []
    for key, spec in JOB_REGISTRY.items():
        # Get latest log for this job
        log_stmt = (
            select(AutomationJobLog)
            .where(AutomationJobLog.job_name == key)
            .order_by(desc(AutomationJobLog.start_time))
            .limit(1)
        )
        log_res = await db.execute(log_stmt)
        latest_log = log_res.scalar_one_or_none()

        output.append(
            {
                "key": key,
                "title": spec["title"],
                "title_en": spec["title_en"],
                "description": spec["description"],
                "cron": spec["cron"],
                "is_enabled": True,
                "last_run": {
                    "id": str(latest_log.id) if latest_log else None,
                    "status": latest_log.status if latest_log else "idle",
                    "start_time": latest_log.start_time.isoformat() if latest_log and latest_log.start_time else None,
                    "duration_ms": latest_log.duration_ms if latest_log else 0,
                    "items_processed": latest_log.items_processed if latest_log else 0,
                    "message": latest_log.message if latest_log else "لم يتم التشغيل بعد",
                }
                if latest_log
                else None,
            }
        )
    return output


@router.post("/cron/{job_name}")
async def scheduled_job(job_name: str, x_cron_secret: str | None = Header(default=None),
                        db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Run a platform job for the scheduler (.github/workflows/jobs.yml), authenticated by
    CRON_SECRET. No workspace is bound: each job goes through every workspace itself."""
    import hmac

    from app.core.config import settings

    if not settings.CRON_SECRET or not hmac.compare_digest(x_cron_secret or "", settings.CRON_SECRET):
        raise HTTPException(status_code=403, detail="Forbidden")
    if job_name not in JOB_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Job '{job_name}' not found.")
    return await run_job(job_name, db)


@router.post("/run/{job_name}")
async def trigger_job(
    job_name: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_superadmin),
) -> dict[str, Any]:
    """Run a job now. Platform staff only: the jobs act on every workspace."""
    if job_name not in JOB_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Job '{job_name}' not found.")

    res = await run_job(job_name, db, tenant_id=str(user.tenant_id) if user.tenant_id else None)
    return res


@router.post("/run-all")
async def trigger_all_jobs(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_superadmin),
) -> dict[str, Any]:
    """Execute all registered automation worker tasks immediately."""
    results = await run_all_jobs(db)
    return {"status": "success", "executed_jobs": results}


@router.get("/logs")
async def list_job_logs(
    limit: int = Query(25, ge=1, le=100),
    job_name: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Retrieve history of background automation execution logs."""
    stmt = select(AutomationJobLog).order_by(desc(AutomationJobLog.start_time)).limit(limit)
    if job_name:
        stmt = stmt.where(AutomationJobLog.job_name == job_name)

    res = await db.execute(stmt)
    logs = res.scalars().all()

    return [
        {
            "id": str(log.id),
            "job_name": log.job_name,
            "status": log.status,
            "start_time": log.start_time.isoformat() if log.start_time else None,
            "end_time": log.end_time.isoformat() if log.end_time else None,
            "duration_ms": log.duration_ms,
            "items_processed": log.items_processed,
            "message": log.message,
            "error_details": log.error_details,
        }
        for log in logs
    ]
