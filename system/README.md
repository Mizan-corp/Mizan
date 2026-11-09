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
- Owns schema bootstrap (`create_all`) and the tracked migrations run by `python manage.py db migrate`.
- Tests: `backend/tests/` (pytest) and the live API suite in `/e2e`.

## On site (single device and LAN)

The same API and app also run on the client's own computer (ADR-005, `installer/`):

- **Backend**: with `MIZAN_MODE=desktop|lan`, `main.py` wraps the API in server mode
  (`shared/backend/app/onprem/`): one address serves `/api/*` and the built app, writes are
  refused while the licence is expired or revoked, and the install checks in with the cloud
  when online. `/api/onprem/status`, `/licence`, `/check-in`, and `/ca.crt` (LAN: the
  certificate tills install).
- **Frontend**: the on-site build (`VITE_DEPLOYMENT=onprem VITE_API_URL=/api`, made by
  `installer/build.py`) has the workspace's own `/login` (with the certificate help on a
  LAN, no cloud sign-up link) and a licence banner (`OnPremLicenceBanner`) where an admin
  enters a new key or checks now.
