"""Help Desk v1 contract primitives, not mounted endpoints or a migration.

All features belong to the module and exist in every variation. Source adapters
accept already-authorized records only; they neither query nor grant access.
Legacy status and identity stay lossless. No customer/contact/financial fields
are included in the common summary by reflection.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

CONTRACT_VERSION = 1
FEATURES = frozenset({"service_catalog", "work_completion", "work_intake"})


def feature_state(saved: Mapping[str, Any] | None) -> dict[str, bool]:
    """Strict module state. Deliberately has no variation/activity parameter.

    Unknown keys fail instead of being silently lost. Missing values are off;
    a store must preserve this state independently when a variation changes.
    """
    if saved is None:
        saved = {}
    if not isinstance(saved, Mapping):
        raise ValueError("feature state must be a mapping")
    if set(saved) - FEATURES:
        raise ValueError("unknown Help Desk feature")
    if any(type(value) is not bool for value in saved.values()):
        raise ValueError("feature values must be booleans")
    return {name: saved.get(name, False) for name in sorted(FEATURES)}


def update_features(saved: Mapping[str, Any] | None, patch: Mapping[str, Any]) -> dict[str, bool]:
    """Partial update, without changing the caller's saved state."""
    current = feature_state(saved)
    if not isinstance(patch, Mapping):
        raise ValueError("feature patch must be a mapping")
    feature_state(patch)
    return {**current, **patch}


@dataclass(frozen=True)
class WorkSummary:
    contract_version: int
    source_module: str
    source_table: str
    source_id: str
    tenant_id: str
    reference: str
    description: str
    source_status: str


# Explicit, audited projection. These are source field maps, not new row models.
_SOURCES = {
    "field_service": ("fsm_work_orders", "order_ref", "issue_description"),
    "real_estate": ("rec_maintenance_tickets", "ticket_ref", "description"),
}


def source_work_summary(source_module: str, record: Mapping[str, Any], *, tenant_id: str) -> WorkSummary:
    """Project an already-authorized source row, retaining native status.

    Tenant equality is a defense, not permission. The caller remains responsible
    for source-module activation, effective role, record access and audit policy.
    No common state enum or write-through transition is invented here.
    """
    if source_module not in _SOURCES:
        raise ValueError("unsupported Help Desk source")
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError("explicit tenant required")
    if str(record.get("tenant_id", "")) != tenant_id:
        raise ValueError("source tenant mismatch")
    table, reference_field, description_field = _SOURCES[source_module]
    values = [record.get(key) for key in ("id", reference_field, description_field, "status")]
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError("incomplete source work record")
    source_id, reference, description, status = values
    return WorkSummary(CONTRACT_VERSION, source_module, table, source_id,
                       tenant_id, reference, description, status)
