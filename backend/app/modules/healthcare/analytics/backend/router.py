from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date
from typing import Dict, Any

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import HealthcareDailyMetric

router = APIRouter(prefix="/api/healthcare/analytics", tags=["Healthcare - Analytics (HLT-24)"])

@router.get("/dashboard")
async def get_dashboard_kpis(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)) -> Dict[str, Any]:
    return {
        "bed_occupancy_rate": 78.5,
        "average_length_of_stay_days": 3.8,
        "daily_patient_visits": 142,
        "emergency_triage_count": 28,
        "pending_critical_labs": 2,
        "doctor_utilization_rate": 86.4,
        "patient_satisfaction_score": 4.8,
    }
