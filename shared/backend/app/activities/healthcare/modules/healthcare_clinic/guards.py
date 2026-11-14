"""Healthcare & Clinic/Hospital ERP: the route guards, shared by router.py and routes/.

Each guard checks the permission its name says (#131). The umbrella "clinic" (admin, manager)
passes them all; the standard clinical roles don't hold it. Patient-level access to clinical data
is separate and never follows the umbrella (service.py, #113).
"""
from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status

from app.dependencies import get_current_user
from app.platform.auth.models.user import User


async def get_current_tenant_id(user: User = Depends(get_current_user)) -> uuid.UUID:
    return user.tenant_id


def _has_clinic_perm(user: User, *perms: str) -> bool:
    """With no specific permission asked, 'clinic:view' is enough."""
    granted = getattr(user, "effective_permissions", frozenset())
    if "clinic" in granted:
        return True
    if not perms:
        return "clinic:view" in granted
    return any(p in granted for p in perms)


def _clinic_guard(*perms: str, detail: str):
    async def guard(current_user: User = Depends(get_current_user)) -> User:
        if not _has_clinic_perm(current_user, *perms):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
        return current_user
    return guard


# Everyone in the clinic: the patient list (demographics), appointments, beds, summary.
require_clinic_view = _clinic_guard(detail="لا تملك صلاحية الوصول إلى العيادات")
# Front desk: register and edit patients, cancel and reschedule, care teams, departments and rosters.
require_clinic_manage = _clinic_guard("clinic:manage", detail="لا تملك صلاحية إدارة المواعيد وملفات المرضى (clinic:manage)")
# Booking: the front desk, and doctors booking follow-ups.
require_clinic_booking = _clinic_guard("clinic:manage", "clinic:doctor", detail="لا تملك صلاحية حجز المواعيد")
# Moving a patient through the queue (waiting, in consultation, completed).
require_clinic_queue = _clinic_guard("clinic:manage", "clinic:doctor", "clinic:nurse",
                                     detail="لا تملك صلاحية تحديث حالة الموعد في قائمة الانتظار")
# Examining, prescribing, ordering tests and referring.
require_clinic_doctor = _clinic_guard("clinic:doctor", detail="لا تملك صلاحية الطبيب السريري (clinic:doctor)")
# The ward: admitting, discharging and readying beds.
require_clinic_ward = _clinic_guard("clinic:nurse", "clinic:manage", detail="لا تملك صلاحية إدارة أسرّة التنويم (clinic:nurse)")
require_clinic_dispense = _clinic_guard("clinic:dispense", detail="لا تملك صلاحية صرف الأدوية والصيدلية (clinic:dispense)")
# Recording and signing off lab results.
require_clinic_lab = _clinic_guard("clinic:lab", detail="لا تملك صلاحية تسجيل نتائج المختبر (clinic:lab)")
require_clinic_billing = _clinic_guard("clinic:billing", detail="لا تملك صلاحية فواتير العيادة (clinic:billing)")
