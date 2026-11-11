"""Platform-Wide Access Control & Authorization Models (RBAC + ABAC Suite).

Distinguishes between:
1. Positions (Job Titles): What the employee does in the organization (Grouped A-I).
2. Account Types: Identity category of system account (Employee, Patient, Admin, etc.).
3. Roles & Permissions: What the user is allowed to access and perform.

Enforces:
- Clinical vs Technical barrier (Administrators cannot access sensitive medical records without explicit clinical role/emergency break-glass).
- ABAC Scoping: Permissions constrained by Facility, Department, and Patient assignments.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, date
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer,
    String, Table, Text, UniqueConstraint, func, text, Index
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.platform.tenancy.context import TenantScoped
from app.db.base import Base

import app.platform.auth.models.user  # noqa: F401 (Ensures User is registered in SQLAlchemy mapper)

if TYPE_CHECKING:
    from app.platform.auth.models.user import User


class AccountType(str, enum.Enum):
    EMPLOYEE = "employee"
    PATIENT = "patient"
    GUARDIAN = "guardian"
    EXTERNAL_PHYSICIAN = "external_physician"
    INSURANCE_PROVIDER = "insurance_provider"
    SUPPLIER = "supplier"
    PARTNER = "partner"
    SERVICE_ACCOUNT = "service_account"
    ADMINISTRATOR = "administrator"


class PositionCategory(str, enum.Enum):
    EXECUTIVE_ADMIN = "executive_admin"
    MEDICAL_STAFF = "medical_staff"
    NURSING_STAFF = "nursing_staff"
    LAB_RADIOLOGY = "lab_radiology"
    PHARMACY = "pharmacy"
    FINANCE_INSURANCE = "finance_insurance"
    HUMAN_RESOURCES = "human_resources"
    PROCUREMENT_MAINTENANCE = "procurement_maintenance"
    IT_TECHNICAL = "it_technical"


class OrgPosition(Base):
    """Standardized and custom organizational job titles (Groups A through I)."""
    __tablename__ = "org_positions"
    __table_args__ = (
        # A workspace's own positions are unique within it; standard ones per (activity, code) (v58/v59).
        Index("uq_org_positions_workspace", "tenant_id", "code", unique=True, postgresql_where=text("tenant_id IS NOT NULL")),
        Index("uq_org_positions_standard", "activity", "code", unique=True, postgresql_where=text("tenant_id IS NULL")),
        Index("idx_org_positions_cat", "category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)  # Null = standard platform position
    # Standard positions: the activity they belong to ('general' = every business), ADR-006 D4.
    activity: Mapped[Optional[str]] = mapped_column(String(48), nullable=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    name_en: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default=PositionCategory.EXECUTIVE_ADMIN.value)
    department_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user_assignments: Mapped[List["UserPosition"]] = relationship("UserPosition", back_populates="position", cascade="all, delete-orphan")


class SysPermission(Base):
    """Granular permissions catalogue across healthcare and operational modules."""
    __tablename__ = "sys_permissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # e.g. emr.sign, patients.create
    module: Mapped[str] = mapped_column(String(64), nullable=False)            # e.g. emr, patients, billing, hr
    action: Mapped[str] = mapped_column(String(32), nullable=False)            # e.g. view, create, sign, dispense
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    name_en: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_clinical: Mapped[bool] = mapped_column(Boolean, default=False)          # Guard against unauthorized technical admin access
    data_sensitivity: Mapped[str] = mapped_column(String(32), default="normal") # normal, sensitive, restricted, critical
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    role_links: Mapped[List["SysRolePermission"]] = relationship("SysRolePermission", back_populates="permission", cascade="all, delete-orphan")


class SysRole(Base):
    """Role definition (RBAC) configured at platform level or customized per tenant."""
    __tablename__ = "sys_roles"
    __table_args__ = (
        UniqueConstraint("code", "tenant_id", name="uq_sys_role_code_tenant"),
        Index("idx_sys_roles_tenant", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)  # Null = system standard role
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    name_en: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_clinical: Mapped[bool] = mapped_column(Boolean, default=False)
    # The role's permissions (ids declared in module manifests). ADR-006 phase 3.
    grants: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    # The role's screens: home, menu and dashboard (ADR-006 phase 5; edited in the builder).
    layout: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    permissions: Mapped[List["SysRolePermission"]] = relationship("SysRolePermission", back_populates="role", cascade="all, delete-orphan", lazy="selectin")
    user_assignments: Mapped[List["UserRoleAssignment"]] = relationship("UserRoleAssignment", back_populates="role", cascade="all, delete-orphan")


class SysRolePermission(Base):
    """Mapping between roles and granular permissions."""
    __tablename__ = "sys_role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sys_roles.id", ondelete="CASCADE"), nullable=False)
    permission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sys_permissions.id", ondelete="CASCADE"), nullable=False)

    role: Mapped["SysRole"] = relationship("SysRole", back_populates="permissions")
    permission: Mapped["SysPermission"] = relationship("SysPermission", back_populates="role_links", lazy="joined")


class UserPosition(Base, TenantScoped):
    """Employee position / job title assignment within a tenant."""
    __tablename__ = "user_positions"
    __table_args__ = (
        Index("idx_user_positions_user", "user_id"),
        Index("idx_user_positions_tenant", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    position_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org_positions.id", ondelete="CASCADE"), nullable=False)
    department_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    department_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, default=date.today)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="positions")
    position: Mapped["OrgPosition"] = relationship("OrgPosition", back_populates="user_assignments", lazy="joined")


class UserRoleAssignment(Base, TenantScoped):
    """Role assignment to a user, with optional ABAC facility and department scoping."""
    __tablename__ = "user_role_assignments"
    __table_args__ = (
        Index("idx_user_role_assign_user", "user_id"),
        Index("idx_user_role_assign_role", "role_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sys_roles.id", ondelete="CASCADE"), nullable=False)
    facility_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)     # NULL = all facilities
    department_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)   # NULL = all departments
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="role_assignments")
    role: Mapped["SysRole"] = relationship("SysRole", back_populates="user_assignments", lazy="joined")


class UserFacilityAssignment(Base, TenantScoped):
    """Physical branch, hospital facility, and department assignment (ABAC boundary)."""
    __tablename__ = "user_facility_assignments"
    __table_args__ = (
        Index("idx_user_facility_assign_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    facility_id: Mapped[int] = mapped_column(Integer, nullable=False)
    facility_name: Mapped[str] = mapped_column(String(150), nullable=False)
    department_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    department_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    can_switch_facility: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="facility_assignments")


class UserPermissionOverride(Base, TenantScoped):
    """Explicit permission override (allow or deny) taking precedence over roles."""
    __tablename__ = "user_permission_overrides"
    __table_args__ = (
        UniqueConstraint("user_id", "permission_id", name="uq_user_perm_override"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    permission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sys_permissions.id", ondelete="CASCADE"), nullable=False)
    override_type: Mapped[str] = mapped_column(String(16), nullable=False)  # "allow" | "deny"
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    granted_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="permission_overrides")
    permission: Mapped["SysPermission"] = relationship("SysPermission", lazy="joined")


class PatientAccessAssignment(Base, TenantScoped):
    """ABAC: Associates clinical staff with specific patients, encounters, or admissions."""
    __tablename__ = "patient_access_assignments"
    __table_args__ = (
        Index("idx_pt_access_user", "user_id"),
        Index("idx_pt_access_patient", "patient_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    patient_id: Mapped[int] = mapped_column(Integer, nullable=False)
    encounter_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    admission_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    assignment_type: Mapped[str] = mapped_column(String(32), default="primary_physician")  # primary_physician, consultant, nurse, on_call, referral
    access_level: Mapped[str] = mapped_column(String(32), default="full")                  # full, read_only, prescribe_only
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="patient_assignments")


class TemporaryAccessGrant(Base, TenantScoped):
    """Emergency 'Break-Glass' or time-limited delegation access grant."""
    __tablename__ = "temporary_access_grants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_patient_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    target_facility_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    grant_reason: Mapped[str] = mapped_column(Text, nullable=False)
    granted_role_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("sys_roles.id"), nullable=True)
    granted_permissions: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    authorized_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserAccessAudit(Base, TenantScoped):
    """HIPAA/GDPR Grade audit log for sensitive clinical and administrative operations."""
    __tablename__ = "user_access_audits"
    __table_args__ = (
        Index("idx_access_audit_user", "user_id"),
        Index("idx_access_audit_resource", "resource_type", "resource_id"),
        Index("idx_access_audit_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    account_type: Mapped[str] = mapped_column(String(32), default=AccountType.EMPLOYEE.value)
    action: Mapped[str] = mapped_column(String(64), nullable=False)  # view_emr, create_order, sign_prescription, etc.
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False) # patient, encounter, lab_result, etc.
    resource_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_clinical: Mapped[bool] = mapped_column(Boolean, default=False)
    decision: Mapped[str] = mapped_column(String(16), default="granted") # granted, denied, break_glass
    facility_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
