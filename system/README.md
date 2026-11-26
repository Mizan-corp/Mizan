# Mizan System: the ERP

What every workspace uses every day: POS, sales, inventory, purchasing, finance, HR,
reports, the 48 industry modules, and public storefronts.

| | Folder | Local | Production |
|---|---|---|---|
| Frontend | `frontend/` | `npm run dev:system` → http://localhost:5173 (`/c/<workspace>`) | `https://<workspace>.allmizan.live` |
| API | `backend/` | `docker compose up system-api` → :8000 | https://api.allmizan.live/api |

- **Backend** is `main.py` + `system_api/` (the route list, tenant resolution, tenant-side
  platform endpoints). Models, services, ERP routers and modules come from `system/core/backend`.
- **Frontend** owns the app shell, ERP screens, tenant routing and `src/activities/<activity>/{modules,variants}/`
  (each activity's screens, ADR-010). Kit components, the API client and stores come from `system/core/frontend` (`@/`).
- Accepts sessions handed off by the website (new owner after onboarding) and the admin
  panel (impersonation) through `#session=` on first load.
- Owns schema bootstrap (`create_all`) and the tracked migrations run by `python manage.py db migrate`.
- Applies the workspace's theme pack (from the workspace resolve and `/auth/me`); the module
  centre (`src/platform/marketplace/screens/`) holds the themes section and developers' modules
  (`src/platform/themes/`, `src/platform/community/`), and `/x/<module>/<entity>` renders a
  community module's records.
- Serves `/ext/v1` for developers' module servers (ADR-007).
- Tests: `backend/tests/` (pytest), the live API suite in `/e2e` and the browser flows in `/e2e/browser`.

## On site (single device and LAN)

The same API and app also run on the client's own computer (ADR-005, `installer/`):

- **Backend**: with `MIZAN_MODE=desktop|lan`, `main.py` wraps the API in server mode
  (`system/core/backend/app/onprem/`): one address serves `/api/*` and the built app, writes are
  refused while the licence is expired or revoked, and the install checks in with the cloud
  when online. `/api/onprem/status`, `/licence`, `/check-in`, and `/ca.crt` (LAN: the
  certificate tills install).
- **Frontend**: the on-site build (`VITE_DEPLOYMENT=onprem VITE_API_URL=/api`, made by
  `installer/build.py`) has the workspace's own `/login` (with the certificate help on a
  LAN, no cloud sign-up link) and a licence banner (`OnPremLicenceBanner`) where an admin
  enters a new key or checks now.
