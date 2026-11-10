"""REST API Router for Platform-Wide Authorization, RBAC & ABAC Suite.

Endpoints:
- /api/authz/account-types: Standard identity categories (Employee, Patient, Admin, etc.)
- /api/authz/positions: Organizational job titles catalogue (Groups A through I)
- /api/authz/roles: Standard and tenant-custom RBAC roles
- /api/authz/permissions: Granular permissions matrix
- /api/authz/users/{user_id}/effective-permissions: Dynamic RBAC+ABAC access resolver
- /api/authz/users/{user_id}/assign-position: Assign organizational position
- /api/authz/users/{user_id}/assign-role: Assign role with facility/department scope
- /api/authz/users/{user_id}/assign-facility: Assign branch/facility and department
- /api/authz/users/{user_id}/permission-override: Set explicit allow/deny override
- /api/authz/patient-assignments: ABAC treating doctor/nurse to patient binding
- /api/authz/break-glass: Emergency clinical break-glass protocol
- /api/authz/audit-logs: HIPAA/GDPR clinical & administrative access audit trail
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.base import get_db
from app.dependencies import get_current_user, require_perm
from app.platform.auth.models.user import User
from app.platform.permissions.models import (
    AccountType, PositionCategory, OrgPosition, SysPermission,
    SysRole, SysRolePermission, UserPosition, UserRoleAssignment,
    UserFacilityAssignment, UserPermissionOverride,
    PatientAccessAssignment, TemporaryAccessGrant, UserAccessAudit
)
from app.platform.permissions.engine import AuthorizationEngine, EffectiveAccessProfile
from app.platform.permissions.catalog import (
    STANDARD_POSITIONS, STANDARD_ACCOUNT_TYPES,
    STANDARD_PERMISSIONS, STANDARD_ROLES, seed_rbac_catalog
)

router = APIRouter(prefix="/authz", tags=["Platform Authorization & Access Control"])


# -------------------------------------------------------------------------
# Request / Response Schemas
# -------------------------------------------------------------------------
class PositionAssignRequest(BaseModel):
    position_id: uuid.UUID
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    start_date: Optional[date] = None
    is_primary: bool = True


class RoleAssignRequest(BaseModel):
    role_id: uuid.UUID
    facility_id: Optional[int] = None      # ABAC Facility boundary (None = all)
    department_id: Optional[int] = None    # ABAC Department boundary (None = all)
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None


class FacilityAssignRequest(BaseModel):
    facility_id: int
    facility_name: str
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    is_primary: bool = True
    can_switch_facility: bool = False


class PermissionOverrideRequest(BaseModel):
    permission_code: str
    override_type: str = Field(pattern="^(allow|deny)$")
    reason: Optional[str] = None
    expires_at: Optional[datetime] = None


class PatientAssignmentRequest(BaseModel):
    user_id: uuid.UUID
    patient_id: int
    encounter_id: Optional[int] = None
    admission_id: Optional[int] = None
    assignment_type: str = "primary_physician"  # primary_physician, consultant, nurse, on_call, referral
    access_level: str = "full"                 # full, read_only, prescribe_only


class BreakGlassRequest(BaseModel):
    target_patient_id: Optional[int] = None
    target_facility_id: Optional[int] = None
    grant_reason: str = Field(min_length=10, description="Detailed medical justification for emergency break-glass override")
    duration_hours: int = Field(default=4, ge=1, le=24)


# -------------------------------------------------------------------------
# 1. Catalog Endpoints
# -------------------------------------------------------------------------
@router.get("/account-types")
async def list_account_types():
    """List standard system account types and their intended isolation purposes."""
    return {
        "account_types": STANDARD_ACCOUNT_TYPES,
        "isolation_policy": {
            "technical_vs_clinical": "Administrator accounts are strictly isolated from patient clinical records (EMR/Prescriptions) unless an explicit clinical role or break-glass grant is activated."
        }
    }


@router.get("/positions")
async def list_positions(
    category: Optional[str] = None,
    q: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List organizational positions (Job Titles across Groups A through I)."""
    stmt = select(OrgPosition).where(OrgPosition.is_active == True)
    if category:
        stmt = stmt.where(OrgPosition.category == category)
    if q:
        query = f"%{q}%"
        stmt = stmt.where(or_(OrgPosition.name.ilike(query), OrgPosition.name_en.ilike(query), OrgPosition.code.ilike(query)))
    stmt = stmt.order_by(OrgPosition.category, OrgPosition.name_en)
    res = await db.execute(stmt)
    positions = res.scalars().all()

    # If database not yet seeded, fallback to standard catalog
    if not positions:
        return [p for p in STANDARD_POSITIONS if (not category or p["category"] == category)]

    return [
        {
            "id": str(p.id),
            "code": p.code,
            "name": p.name,
            "name_en": p.name_en,
            "category": p.category,
            "department_name": p.department_name,
            "description": p.description,
        }
        for p in positions
    ]


@router.get("/roles")
async def list_roles(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List available RBAC roles and their associated permissions."""
    stmt = (
        select(SysRole)
        .options(selectinload(SysRole.permissions).selectinload(SysRolePermission.permission))
        .order_by(SysRole.is_system.desc(), SysRole.name_en)
    )
    res = await db.execute(stmt)
    roles = res.scalars().all()

    if not roles:
        return STANDARD_ROLES

    return [
        {
            "id": str(r.id),
            "code": r.code,
            "name": r.name,
            "name_en": r.name_en,
            "description": r.description,
            "is_system": r.is_system,
            "is_clinical": r.is_clinical,
            "permissions": [rp.permission.code for rp in r.permissions if rp.permission],
        }
        for r in roles
    ]


@router.get("/permissions")
async def list_permissions(
    module: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List granular system permissions grouped by module."""
    stmt = select(SysPermission)
    if module:
        stmt = stmt.where(SysPermission.module == module)
    stmt = stmt.order_by(SysPermission.module, SysPermission.code)
    res = await db.execute(stmt)
    perms = res.scalars().all()

    if not perms:
        return [p for p in STANDARD_PERMISSIONS if (not module or p["module"] == module)]

    return [
        {
            "id": str(p.id),
            "code": p.code,
            "module": p.module,
            "action": p.action,
            "name": p.name,
            "name_en": p.name_en,
            "description": p.description,
            "is_clinical": p.is_clinical,
            "data_sensitivity": p.data_sensitivity,
        }
        for p in perms
    ]


# -------------------------------------------------------------------------
# 2. Real-Time Effective Access Evaluation (RBAC + ABAC)
# -------------------------------------------------------------------------
@router.get("/users/{user_id}/effective-permissions")
async def get_effective_user_permissions(
    user_id: uuid.UUID,
    facility_id: Optional[int] = None,
    department_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compute effective permissions for a user across roles, overrides, and ABAC scopes."""
    target_user = await db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    is_super = getattr(current_user, "is_superadmin", False)
    if not is_super and target_user.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="لا يمكن الاطلاع على صلاحيات مستخدم في منشأة أخرى")

    if not is_super and current_user.id != target_user.id and current_user.role not in ("admin", "manager", "superadmin", "owner") and "users" not in (current_user.permissions or []):
        raise HTTPException(status_code=403, detail="غير مصرح لك بالاطلاع على صلاحيات مستخدمين آخرين")

    profile = await AuthorizationEngine.get_effective_profile(
        db=db,
        user=target_user,
        facility_id=facility_id,
        department_id=department_id,
    )

    return {
        "user_id": str(profile.user_id),
        "username": profile.username,
        "full_name": profile.full_name,
        "account_type": profile.account_type,
        "is_superadmin": profile.is_superadmin,
        "has_break_glass": profile.has_break_glass,
        "positions": profile.positions,
        "roles": profile.roles,
        "permissions_count": len(profile.permissions),
        "permissions": sorted(list(profile.permissions)),
        "clinical_permissions": sorted(list(profile.clinical_permissions)),
        "accessible_facility_ids": list(profile.accessible_facility_ids),
        "accessible_department_ids": list(profile.accessible_department_ids),
        "assigned_patient_ids": list(profile.assigned_patient_ids),
    }


# -------------------------------------------------------------------------
# 3. User Assignment Endpoints (Positions, Roles, Facilities, Overrides)
# -------------------------------------------------------------------------
@router.post("/users/{user_id}/assign-position")
async def assign_user_position(
    user_id: uuid.UUID,
    data: PositionAssignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("users", "admin")),
):
    """Assign an organizational job title to an employee."""
    target_user = await db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    is_super = getattr(current_user, "is_superadmin", False)
    if not is_super and target_user.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="لا يمكن تعديل صلاحيات مستخدم في منشأة أخرى")

    position = await db.get(OrgPosition, data.position_id)
    if not position:
        raise HTTPException(status_code=404, detail="المسمى الوظيفي غير موجود")

    # If primary, unmark existing primary positions
    if data.is_primary:
        await db.execute(
            text("UPDATE user_positions SET is_primary = false WHERE user_id = :uid"),
            {"uid": user_id}
        )

    assignment = UserPosition(
        tenant_id=target_user.tenant_id,
        user_id=user_id,
        position_id=data.position_id,
        department_id=data.department_id,
        department_name=data.department_name or position.department_name,
        start_date=data.start_date or date.today(),
        is_primary=data.is_primary,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)

    return {
        "status": "ok",
        "message": f"تم تعيين المسمى الوظيفي '{position.name}' للموظف بنجاح",
        "assignment_id": str(assignment.id),
    }


@router.post("/users/{user_id}/assign-role")
async def assign_user_role(
    user_id: uuid.UUID,
    data: RoleAssignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("users", "admin")),
):
    """Assign an RBAC role with optional facility and department ABAC boundaries."""
    target_user = await db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    is_super = getattr(current_user, "is_superadmin", False)
    if not is_super and target_user.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="لا يمكن تعديل صلاحيات مستخدم في منشأة أخرى")

    role = await db.get(SysRole, data.role_id)
    if not role:
        raise HTTPException(status_code=404, detail="الدور غير موجود")

    assignment = UserRoleAssignment(
        tenant_id=target_user.tenant_id,
        user_id=user_id,
        role_id=data.role_id,
        facility_id=data.facility_id,
        department_id=data.department_id,
        valid_from=data.valid_from,
        valid_until=data.valid_until,
        is_active=True,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)

    return {
        "status": "ok",
        "message": f"تم إسناد الدور '{role.name}' بنجاح مع العزل المحدد",
        "assignment_id": str(assignment.id),
    }


@router.post("/users/{user_id}/assign-facility")
async def assign_user_facility(
    user_id: uuid.UUID,
    data: FacilityAssignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("users", "admin")),
):
    """Assign a user to a physical facility and department."""
    target_user = await db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    is_super = getattr(current_user, "is_superadmin", False)
    if not is_super and target_user.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="لا يمكن تعديل صلاحيات مستخدم في منشأة أخرى")

    assignment = UserFacilityAssignment(
        tenant_id=target_user.tenant_id,
        user_id=user_id,
        facility_id=data.facility_id,
        facility_name=data.facility_name,
        department_id=data.department_id,
        department_name=data.department_name,
        is_primary=data.is_primary,
        can_switch_facility=data.can_switch_facility,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)

    return {
        "status": "ok",
        "message": f"تم ربط المستخدم بالمنشأة '{data.facility_name}'",
        "assignment_id": str(assignment.id),
    }


@router.post("/users/{user_id}/permission-override")
async def set_permission_override(
    user_id: uuid.UUID,
    data: PermissionOverrideRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("users", "admin")),
):
    """Set an explicit permission override (allow or deny) taking precedence over roles."""
    target_user = await db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    is_super = getattr(current_user, "is_superadmin", False)
    if not is_super and target_user.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="لا يمكن تعديل صلاحيات مستخدم في منشأة أخرى")

    res_p = await db.execute(select(SysPermission).where(SysPermission.code == data.permission_code))
    perm = res_p.scalar_one_or_none()
    if not perm:
        raise HTTPException(status_code=404, detail="الصلاحية غير موجودة")

    # Upsert override
    res_ex = await db.execute(
        select(UserPermissionOverride).where(
            UserPermissionOverride.user_id == user_id,
            UserPermissionOverride.permission_id == perm.id,
        )
    )
    existing = res_ex.scalar_one_or_none()
    if existing:
        existing.override_type = data.override_type
        existing.reason = data.reason
        existing.granted_by = current_user.id
        existing.expires_at = data.expires_at
    else:
        existing = UserPermissionOverride(
            tenant_id=target_user.tenant_id,
            user_id=user_id,
            permission_id=perm.id,
            override_type=data.override_type,
            reason=data.reason,
            granted_by=current_user.id,
            expires_at=data.expires_at,
        )
        db.add(existing)

    await db.commit()
    return {
        "status": "ok",
        "message": f"تم تطبيق الاستثناء ({data.override_type}) للصلاحية '{data.permission_code}' بنجاح",
    }


# -------------------------------------------------------------------------
# 4. Patient Access Binding (ABAC) & Emergency Break-Glass
# -------------------------------------------------------------------------
@router.post("/patient-assignments")
async def create_patient_access_assignment(
    data: PatientAssignmentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("clinical", "emr", "users", "admin")),
):
    """Bind a physician or nurse to a specific patient or encounter (ABAC patient boundary)."""
    target_user = await db.get(User, data.user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="المستخدم الطبي غير موجود")

    is_super = getattr(current_user, "is_superadmin", False)
    if not is_super and target_user.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="لا يمكن إسناد مريض لمستخدم طبي في منشأة أخرى")

    assignment = PatientAccessAssignment(
        tenant_id=target_user.tenant_id,
        user_id=data.user_id,
        patient_id=data.patient_id,
        encounter_id=data.encounter_id,
        admission_id=data.admission_id,
        assignment_type=data.assignment_type,
        access_level=data.access_level,
        is_active=True,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)

    return {
        "status": "ok",
        "message": f"تم إسناد المريض #{data.patient_id} للطبيب/الممرض بنجاح",
        "assignment_id": str(assignment.id),
    }


@router.post("/break-glass")
async def activate_emergency_break_glass(
    data: BreakGlassRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Emergency 'Break-Glass' protocol granting temporary clinical access with mandatory audit logging."""
    clinical_roles = {"doctor", "nurse", "physician", "surgeon", "consultant", "clinical", "admin", "manager", "superadmin"}
    is_clinical_user = (
        current_user.role in clinical_roles
        or getattr(current_user, "is_superadmin", False)
        or any(p in (current_user.permissions or []) for p in ("clinical", "emr", "doctor", "nurse", "medical"))
    )
    if not is_clinical_user:
        raise HTTPException(
            status_code=403,
            detail="بروتوكول كسر زجاج الطوارئ مخصص للكوادر الطبية والمصرح لهم سريرياً فقط",
        )

    if not data.grant_reason or len(data.grant_reason.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="يجب تقديم مبرر طبي طارئ كافٍ وموثق (لا يقل عن 10 أحرف) لتفعيل كسر الزجاج",
        )

    now = datetime.utcnow()
    duration = min(max(data.duration_hours, 1), 4)  # Clamp duration between 1 and 4 hours
    expires = now + timedelta(hours=duration)

    grant = TemporaryAccessGrant(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        target_patient_id=data.target_patient_id,
        target_facility_id=data.target_facility_id,
        grant_reason=data.grant_reason.strip(),
        granted_permissions=["emr.view", "emr.create", "prescriptions.create", "lab.orders.view"],
        authorized_by=current_user.id,
        starts_at=now,
        expires_at=expires,
    )
    db.add(grant)
    await db.commit()

    # Log critical audit
    client_ip = request.client.host if request.client else None
    await AuthorizationEngine.log_access_audit(
        db=db,
        user=current_user,
        action="break_glass:activate",
        resource_type="emergency_override",
        resource_id=str(data.target_patient_id) if data.target_patient_id else "facility_wide",
        is_clinical=True,
        decision="break_glass",
        ip_address=client_ip,
        details={
            "reason": data.grant_reason,
            "duration_hours": duration,
            "expires_at": expires.isoformat(),
        },
    )

    return {
        "status": "ok",
        "message": f"تم تفعيل بروتوكول كسر زجاج الطوارئ (Emergency Break-Glass) لمدة {duration} ساعات وتوثيقه بالكامل في سجل الامتثال",
        "duration_hours": duration,
        "expires_at": expires.isoformat(),
    }


# -------------------------------------------------------------------------
# 5. Access Audit Trail Viewer
# -------------------------------------------------------------------------
@router.get("/audit-logs")
async def list_access_audit_logs(
    is_clinical: Optional[bool] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("users", "admin", "reports")),
):
    """Retrieve HIPAA/GDPR clinical and administrative access audit trail."""
    stmt = select(UserAccessAudit)
    if not getattr(current_user, "is_superadmin", False):
        stmt = stmt.where(UserAccessAudit.tenant_id == current_user.tenant_id)
    if is_clinical is not None:
        stmt = stmt.where(UserAccessAudit.is_clinical == is_clinical)
    stmt = stmt.order_by(UserAccessAudit.created_at.desc()).limit(limit)
    res = await db.execute(stmt)
    logs = res.scalars().all()

    return [
        {
            "id": str(l.id),
            "user_id": str(l.user_id) if l.user_id else None,
            "account_type": l.account_type,
            "action": l.action,
            "resource_type": l.resource_type,
            "resource_id": l.resource_id,
            "is_clinical": l.is_clinical,
            "decision": l.decision,
            "ip_address": l.ip_address,
            "details": l.details,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ]


@router.post("/seed")
async def seed_authz_catalog_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Seed or update standard positions, roles, and granular permissions."""
    if current_user.role not in ("admin", "superadmin") and not getattr(current_user, "is_superadmin", False):
        raise HTTPException(status_code=403, detail="Admin permissions required")

    await seed_rbac_catalog(db)
    return {
        "status": "ok",
        "message": "تم تهيئة دليل المناصب (98 وظيفة)، الأدوار (20 دور)، والصلاحيات بنجاح",
    }
