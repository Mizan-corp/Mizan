# Mizan Admin (Admoon)

The platform owner's control plane: tenants, provisioning jobs, plans & subscriptions,
billing invoices, backups, infrastructure and monitoring, platform users and audit logs.
Super-admins only.

| | Folder | Local | Production |
|---|---|---|---|
| Frontend | `frontend/` | `npm run dev:admin` → http://localhost:5175 | https://mizan-co-admin.vercel.app |
| API | `backend/` | `docker compose up admin-api` → :8002 | https://mizan-co-admin-api.vercel.app |

- The API mounts `/admoon/*` (all behind `require_superadmin`), `/auth/*` and `/billing/*`.
- `backend/admoon/` holds provisioning, backup and storage/database provider code;
  `backend/admin_api/` holds the router and service.
- Impersonation opens the tenant's workspace in the system app signed in as its admin,
  without touching the super-admin's own session.
- Served with `noindex` and `X-Frame-Options: DENY`.
