"""Platform-Wide Authorization & Access Control Engine (RBAC + ABAC).

Enforces:
1. Role-Based Access Control (RBAC): Base permissions derived from assigned roles.
2. Attribute-Based Access Control (ABAC): Dynamic constraints based on:
   - Account Type (Employee, Administrator, Patient, etc.)
   - Organization / Branch / Facility Scoping
   - Department Scoping
   - Patient / Encounter Assignments (Treating Doctor, Primary Nurse)
3. Clinical vs Administrative Isolation:
   - Technical administrators are explicitly prevented from viewing protected health
     information (PHI / EMR) unless granted explicit clinical credentialing or emergency break-glass.
4. Emergency 'Break-Glass' Override Protocols:
   - Time-limited emergency access with mandatory audit trail.
5. HIPAA / GDPR Access Auditing:
   - Complete access logs with decision, resource ID, client IP, and clinical flags.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Set, List, Dict, Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.base import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.auth_access import (
    AccountType, OrgPosition, SysPermission, SysRole,
    SysRolePermission, UserPosition, UserRoleAssignment,
    UserFacilityAssignment, UserPermissionOverride,
    PatientAccessAssignment, TemporaryAccessGrant, UserAccessAudit
)

logger = logging.getLogger("mizan.authz")


@dataclass
class EffectiveAccessProfile:
    user_id: uuid.UUID
    username: str
    full_name: str
    account_type: str
    positions: List[Dict[str, Any]] = field(default_factory=list)
    roles: List[str] = field(default_factory=list)
    permissions: Set[str] = field(default_factory=set)
    clinical_permissions: Set[str] = field(default_factory=set)
    accessible_facility_ids: Set[int] = field(default_factory=set)
    accessible_department_ids: Set[int] = field(default_factory=set)
    assigned_patient_ids: Set[int] = field(default_factory=set)
    has_break_glass: bool = False
    is_superadmin: bool = False

    def can(self, permission_code: str) -> bool:
        if self.is_superadmin:
            return True
        return permission_code in self.permissions

    def can_access_patient(self, patient_id: int) -> bool:
        if self.is_superadmin or self.has_break_glass:
            return True
        return patient_id in self.assigned_patient_ids


class AuthorizationEngine:
    """Core evaluation engine resolving effective access across RBAC and ABAC dimensions."""

    @classmethod
    async def get_effective_profile(
        cls,
        db: AsyncSession,
        user: User,
        facility_id: Optional[int] = None,
        department_id: Optional[int] = None,
    ) -> EffectiveAccessProfile:
        now = datetime.utcnow()
        is_super = getattr(user, "is_superadmin", False) or user.role == "superadmin"

        profile = EffectiveAccessProfile(
            user_id=user.id,
            username=user.username,
            full_name=user.full_name,
            account_type=getattr(user, "account_type", AccountType.EMPLOYEE.value),
            is_superadmin=is_super,
        )

        # 1. Fetch assigned positions (Job Titles)
        stmt_pos = (
            select(UserPosition)
            .where(UserPosition.user_id == user.id)
            .options(selectinload(UserPosition.position))
        )
        res_pos = await db.execute(stmt_pos)
        user_pos_rows = res_pos.scalars().all()
        for up in user_pos_rows:
            if up.position:
                profile.positions.append({
                    "code": up.position.code,
                    "name": up.position.name,
                    "name_en": up.position.name_en,
                    "category": up.position.category,
                    "department_name": up.department_name or up.position.department_name,
                    "is_primary": up.is_primary,
                })

        # 2. Fetch assigned facilities and departments
        stmt_fac = select(UserFacilityAssignment).where(UserFacilityAssignment.user_id == user.id)
        res_fac = await db.execute(stmt_fac)
        for ufa in res_fac.scalars().all():
            profile.accessible_facility_ids.add(ufa.facility_id)
            if ufa.department_id:
                profile.accessible_department_ids.add(ufa.department_id)

        # 3. Check for active emergency 'Break-Glass' temporary grants
        stmt_grant = (
            select(TemporaryAccessGrant)
            .where(
                TemporaryAccessGrant.user_id == user.id,
                TemporaryAccessGrant.is_revoked == False,
                TemporaryAccessGrant.starts_at <= now,
                TemporaryAccessGrant.expires_at >= now,
            )
        )
        res_grant = await db.execute(stmt_grant)
        active_grants = res_grant.scalars().all()
        if active_grants:
            profile.has_break_glass = True
            for g in active_grants:
                if g.target_patient_id:
                    profile.assigned_patient_ids.add(g.target_patient_id)
                if g.granted_permissions:
                    for p in g.granted_permissions:
                        profile.permissions.add(p)

        # 4. Fetch assigned roles (RBAC) filtered by facility & department scope (ABAC)
        stmt_roles = (
            select(UserRoleAssignment)
            .where(
                UserRoleAssignment.user_id == user.id,
                UserRoleAssignment.is_active == True,
            )
            .options(
                selectinload(UserRoleAssignment.role).selectinload(SysRole.permissions).selectinload(SysRolePermission.permission)
            )
        )
        res_roles = await db.execute(stmt_roles)
        role_assignments = res_roles.scalars().all()

        is_admin_account = profile.account_type == AccountType.ADMINISTRATOR.value

        for ra in role_assignments:
            # Check temporal validity
            if ra.valid_from and ra.valid_from > now:
                continue
            if ra.valid_until and ra.valid_until < now:
                continue

            # Check facility ABAC scope
            if facility_id and ra.facility_id and ra.facility_id != facility_id:
                continue
            # Check department ABAC scope
            if department_id and ra.department_id and ra.department_id != department_id:
                continue

            role = ra.role
            if not role:
                continue

            profile.roles.append(role.code)

            for rp in role.permissions:
                perm = rp.permission
                if not perm:
                    continue

                # Clinical vs Technical Administrator Barrier:
                # An Administrator account cannot inherit clinical EMR permissions directly from administrative roles
                # unless explicitly marked as a clinical role or possessing an active break-glass emergency grant.
                if perm.is_clinical and is_admin_account and not role.is_clinical and not profile.has_break_glass:
                    continue

                profile.permissions.add(perm.code)
                if perm.is_clinical:
                    profile.clinical_permissions.add(perm.code)

        # 5. Apply User Permission Overrides (explicit allow / deny overrides)
        stmt_overrides = (
            select(UserPermissionOverride)
            .where(
                UserPermissionOverride.user_id == user.id,
                or_(UserPermissionOverride.expires_at.is_(None), UserPermissionOverride.expires_at >= now)
            )
            .options(selectinload(UserPermissionOverride.permission))
        )
        res_overrides = await db.execute(stmt_overrides)
        for po in res_overrides.scalars().all():
            if po.permission:
                p_code = po.permission.code
                if po.override_type == "deny":
                    profile.permissions.discard(p_code)
                    profile.clinical_permissions.discard(p_code)
                elif po.override_type == "allow":
                    profile.permissions.add(p_code)
                    if po.permission.is_clinical:
                        profile.clinical_permissions.add(p_code)

        # 6. Fetch assigned patients (ABAC patient boundary)
        stmt_pts = select(PatientAccessAssignment.patient_id).where(
            PatientAccessAssignment.user_id == user.id,
            PatientAccessAssignment.is_active == True,
        )
        res_pts = await db.execute(stmt_pts)
        for pt_id in res_pts.scalars().all():
            profile.assigned_patient_ids.add(pt_id)

        # Fallback for legacy permissions array in users table
        if user.permissions and isinstance(user.permissions, list):
            for legacy_p in user.permissions:
                profile.permissions.add(legacy_p)

        return profile

    @classmethod
    async def log_access_audit(
        cls,
        db: AsyncSession,
        user: User,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        is_clinical: bool = False,
        decision: str = "granted",
        facility_id: Optional[int] = None,
        department_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Record an immutable HIPAA/GDPR audit log entry."""
        try:
            audit = UserAccessAudit(
                tenant_id=user.tenant_id,
                user_id=user.id,
                account_type=getattr(user, "account_type", AccountType.EMPLOYEE.value),
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id else None,
                is_clinical=is_clinical,
                decision=decision,
                facility_id=facility_id,
                department_id=department_id,
                ip_address=ip_address,
                user_agent=user_agent,
                details=details or {},
            )
            db.add(audit)
            await db.commit()
        except Exception as e:
            logger.error("Failed to write access audit log: %s", e)


def require_permission(
    permission_code: str,
    is_clinical: bool = False,
    facility_scoped: bool = False,
):
    """FastAPI dependency factory enforcing granular RBAC & ABAC permissions."""
    async def dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> EffectiveAccessProfile:
        # Extract optional ABAC headers or query params
        facility_id = None
        fac_header = request.headers.get("X-Facility-ID")
        if fac_header and fac_header.isdigit():
            facility_id = int(fac_header)

        dept_id = None
        dept_header = request.headers.get("X-Department-ID")
        if dept_header and dept_header.isdigit():
            dept_id = int(dept_header)

        profile = await AuthorizationEngine.get_effective_profile(
            db=db,
            user=current_user,
            facility_id=facility_id if facility_scoped else None,
            department_id=dept_id,
        )

        client_ip = request.client.host if request.client else None
        ua = request.headers.get("User-Agent")

        if not profile.can(permission_code):
            # Audit denied attempt
            await AuthorizationEngine.log_access_audit(
                db=db,
                user=current_user,
                action=f"check_permission:{permission_code}",
                resource_type="permission",
                resource_id=permission_code,
                is_clinical=is_clinical,
                decision="denied",
                facility_id=facility_id,
                department_id=dept_id,
                ip_address=client_ip,
                user_agent=ua,
                details={"reason": "Missing required granular permission"},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"صلاحية مرفوضة: لا تملك ترخيص تنفيذ الإجراء ({permission_code})"
            )

        # Log authorized clinical access for audit compliance
        if is_clinical:
            await AuthorizationEngine.log_access_audit(
                db=db,
                user=current_user,
                action=f"clinical_access:{permission_code}",
                resource_type="clinical_endpoint",
                resource_id=permission_code,
                is_clinical=True,
                decision="granted",
                facility_id=facility_id,
                department_id=dept_id,
                ip_address=client_ip,
                user_agent=ua,
            )

        return profile

    return dependency


def require_patient_access(permission_code: str):
    """FastAPI dependency enforcing treating physician / assigned nurse ABAC boundary for a patient."""
    async def dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> EffectiveAccessProfile:
        profile = await AuthorizationEngine.get_effective_profile(db=db, user=current_user)

        # Check basic permission
        if not profile.can(permission_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"صلاحية مرفوضة: لا تملك ترخيص السجل الطبي ({permission_code})"
            )

        # Check path parameters for patient_id
        patient_id_raw = request.path_params.get("patient_id") or request.query_params.get("patient_id")
        if patient_id_raw and str(patient_id_raw).isdigit():
            patient_id = int(patient_id_raw)
            if not profile.can_access_patient(patient_id):
                # Audit unauthorized patient access attempt
                client_ip = request.client.host if request.client else None
                await AuthorizationEngine.log_access_audit(
                    db=db,
                    user=current_user,
                    action=f"patient_access_check:{permission_code}",
                    resource_type="patient",
                    resource_id=str(patient_id),
                    is_clinical=True,
                    decision="denied",
                    ip_address=client_ip,
                    details={"reason": "User not assigned to patient and break-glass inactive"},
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"عزل البيانات السريرية: المريض #{patient_id} غير مدرج في كشوفاتك الطبية المباشرة"
                )

        return profile

    return dependency
