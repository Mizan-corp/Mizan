# Mizan Website

The public face of Mizan: landing, product, industries, pricing, blog, the docs portal,
and self-serve signup with the 3-step onboarding wizard.

| | Folder | Local | Production |
|---|---|---|---|
| Frontend | `frontend/` | `npm run dev:website` → http://localhost:5174 | https://mizan-co.vercel.app |
| API | `backend/` | `docker compose up website-api` → :8001 | https://mizan-co-web-api.vercel.app |

- The API exposes only `GET /platform/plans` and `POST /platform/signup` (rate-limited).
  Signup creates the workspace, seeds sector demo data and returns a token.
- The website never holds a session: after onboarding it opens the system app already
  signed in (`openWithSession` in `shared/frontend/src/lib/handoff.ts`).
- "Sign in" links go to the system app's `/login`.
