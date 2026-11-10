"""Row-level multi-tenancy.

Every tenant-owned row carries tenant_id (TenantScoped mixin). Reads and
writes are scoped automatically:

- Reads/updates/deletes: `with_loader_criteria` injects `tenant_id == ctx`
  into every ORM statement while a tenant is in context.
- Inserts: `before_flush` stamps tenant_id from context when left unset.

The context is set by `get_current_user` from the authenticated user, or
explicitly by public routes (storefront) after resolving their tenant.
Scripts and migrations run with no context and see everything.
"""
import logging
import os
import time
import uuid
from contextvars import ContextVar

from sqlalchemy import ForeignKey, event
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, declared_attr, mapped_column, with_loader_criteria

current_tenant_id: ContextVar[uuid.UUID | None] = ContextVar("current_tenant_id", default=None)


class TenantScoped:
    """Mixin for models whose rows belong to exactly one tenant."""

    @declared_attr
    def tenant_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            UUID(as_uuid=True),
            ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )


_tenancy_events_installed = False

# While a workspace is bound, every transaction runs as this role (SET LOCAL ROLE), which has no
# BYPASSRLS: the connection's login role may bypass RLS (Neon's owner, a local superuser), and
# then RLS would not isolate raw SQL at all (#112). Transaction-local, so it is safe behind
# PgBouncer in transaction mode. Scripts and migrations (no workspace bound) keep the login role.
APP_ROLE = os.environ.get("MIZAN_DB_APP_ROLE", "mizan_app")
_role_ready: bool = False
_role_checked_at: float = 0.0


def restrict_to_app_role(connection) -> None:
    """Run the rest of this transaction as APP_ROLE (sync connection; called in a transaction)."""
    global _role_ready, _role_checked_at
    if not APP_ROLE:
        return
    from sqlalchemy import text

    if not _role_ready and time.monotonic() - _role_checked_at > 60:
        _role_checked_at = time.monotonic()
        _role_ready = bool(connection.execute(text(
            "SELECT CASE WHEN EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :r)"
            " THEN pg_has_role(current_user, :r, 'MEMBER') ELSE false END"
        ), {"r": APP_ROLE}).scalar())
        if not _role_ready:
            logging.getLogger("mizan.tenancy").critical(
                "Database role %r is missing or not granted to the login role: workspace isolation "
                "relies on RLS, which this login role may bypass. Apply the migrations (#112).", APP_ROLE)
    if _role_ready:
        connection.exec_driver_sql(f'SET LOCAL ROLE "{APP_ROLE}"')


def install_tenancy_events() -> None:
    """Attach global scoping listeners to the sync Session class (all sessions).

    Idempotent: services built in the same process must not stack listeners.
    """
    global _tenancy_events_installed
    if _tenancy_events_installed:
        return
    _tenancy_events_installed = True

    @event.listens_for(Session, "after_begin")
    def _set_pg_tenant(session, transaction, connection):
        tid = current_tenant_id.get()
        if tid is not None:
            from sqlalchemy import text
            connection.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"),
                {"t": str(tid)},
            )
            restrict_to_app_role(connection)

    @event.listens_for(Session, "do_orm_execute")
    def _scope_statements(execute_state):
        if not (execute_state.is_select or execute_state.is_update or execute_state.is_delete):
            return
        tid = current_tenant_id.get()
        if tid is None:
            return
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                TenantScoped,
                lambda cls: cls.tenant_id == tid,
                include_aliases=True,
            )
        )

    @event.listens_for(Session, "before_flush")
    def _stamp_tenant(session, flush_context, instances):
        tid = current_tenant_id.get()
        for obj in session.new:
            if isinstance(obj, TenantScoped):
                obj_tid = getattr(obj, "tenant_id", None)
                if obj_tid is None:
                    if tid is not None:
                        obj.tenant_id = tid
                elif tid is not None and str(obj_tid) != str(tid):
                    raise PermissionError(
                        f"Tenant isolation mismatch: {obj.__class__.__name__} carrying tenant_id={obj_tid} "
                        f"does not match active tenant_id={tid}"
                    )


async def primary_tenant_id(db) -> uuid.UUID | None:
    """The platform's first (default) workspace — legacy users land here."""
    from sqlalchemy import select

    from app.models.tenant import Tenant

    res = await db.execute(select(Tenant.id).order_by(Tenant.created_at).limit(1))
    return res.scalar()


async def bind_tenant(db, tid: uuid.UUID | None) -> None:
    """Bind the tenant to BOTH the request context (ORM stamping/scoping)
    and the Postgres GUC (RLS — enforces raw SQL too). Uses transaction-local
    setting (true) so the pool automatically clears on commit/rollback."""
    from sqlalchemy import text
    current_tenant_id.set(tid)
    if tid is not None:
        await db.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tid)})
        conn = await db.connection()
        await conn.run_sync(restrict_to_app_role)


async def unbind_tenant(db) -> None:
    from sqlalchemy import text
    current_tenant_id.set(None)
    try:
        await db.execute(text("RESET app.tenant_id"))
        await db.execute(text("RESET app.bypass"))
        await db.execute(text("RESET ROLE"))
    except Exception:
        pass  # connection already gone
