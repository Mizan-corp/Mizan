"""Declared Help Desk source adapters for the unified read view.

The unification direction (2026-11-24 user instruction) brings similar existing
and planned capabilities into Help Desk as one domain. Each source declares
itself here once; the shared read route consumes the registry instead of
hardcoding imports, so a planned source (hotel engineering requests, equipment
maintenance) plugs in without editing Help Desk core, and a source whose code
is absent degrades to an explicit diagnostic instead of an import crash.

Registration is read-side only: it moves no rows, converts no status or price,
and grants nothing. Every adapter's rows still pass the source module's own
activation check and the caller's independently held grants in work.py, and the
source_work_summary contract retains native identity/status per row.
"""
import importlib
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceAdapter:
    id: str
    model_path: str  # "dotted.module:ClassName", imported lazily
    keys: tuple[str, ...]  # ORM attributes read for the common projection


SOURCES: tuple[SourceAdapter, ...] = (
    SourceAdapter(
        "field_service",
        "app.activities.maintenance.modules.field_service.models:FsmWorkOrder",
        ("id", "tenant_id", "order_ref", "issue_description", "status"),
    ),
    SourceAdapter(
        "real_estate",
        "app.activities.property.modules.real_estate.models:RecMaintenanceTicket",
        ("id", "tenant_id", "ticket_ref", "description", "status"),
    ),
)


def load_model(adapter: SourceAdapter):
    """Resolve the adapter's ORM model, or None when its source code is absent
    (a planned/uninstalled source is a diagnostics entry, never a 500)."""
    module_name, _, class_name = adapter.model_path.partition(":")
    try:
        module = importlib.import_module(module_name)
        return getattr(module, class_name)
    except (ImportError, AttributeError):
        return None
