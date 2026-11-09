# Mizan System: the ERP

What every workspace uses every day: POS, sales, inventory, purchasing, finance, HR,
reports, the 48 industry modules, and public storefronts.

| | Folder | Local | Production |
|---|---|---|---|
| Frontend | `frontend/` | `npm run dev:system` → http://localhost:5173 | https://mizan-co-app.vercel.app |
| API | `backend/` | `docker compose up system-api` → :8000 | https://mizan-co-api.vercel.app |

- **Backend** is `main.py` + `system_api/` (the route list, tenant resolution, tenant-side
  platform endpoints). Models, services, ERP routers and modules come from `shared/backend`.
- **Frontend** owns the app shell, ERP screens, tenant routing and `src/modules/` (industry
  screens). Kit components, the API client and stores come from `shared/frontend` (`@/`).
- Accepts sessions handed off by the website (new owner after onboarding) and the admin
  panel (impersonation) through `#session=` on first load.
- Owns schema bootstrap (`create_all`) and the tracked migrations run by `scripts/migrate.py`.
- Tests: `backend/tests/` (pytest) and the live API suite in `/e2e`.
