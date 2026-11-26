# Mizan Website

The public face of Mizan: landing, product, industries, pricing, blog, the user docs,
self-serve signup with the 3-step onboarding wizard, contact, the legal pages, and the
**developer platform** at `dev.allmizan.live`.

| | Folder | Local | Production |
|---|---|---|---|
| Frontend | `frontend/` | `npm run dev:website` → http://localhost:5174 (developer platform: /dev) | https://allmizan.live, https://dev.allmizan.live |
| API | `backend/` | `docker compose up website-api` → :8001 | https://web-api.allmizan.live/api |

- The API exposes `GET /platform/plans` and `POST /platform/signup` (rate-limited), and the
  developer portal's `/developers/*`. Signup creates the owner account and workspace, seeds
  sector demo data and returns a token.
- After onboarding the new owner lands in the **owner panel**, already signed in
  (`openWithSession` in `shared/frontend/src/lib/handoff.ts`).
- "Sign in" goes to `/login`, which forwards to the owner panel's sign-in (`/owner/login`,
  ADR-008); owners come back through `/session`
  here: the website keeps its own copy of the owner's session (`mizan.owner_session`) to
  show "back to panel" and "sign out" instead of "get started" and "sign in".
  `/signout` clears it.

## Legal pages and business details

| Page | Route |
|---|---|
| Terms of Service · شروط الاستخدام | `/terms` |
| Privacy Policy · سياسة الخصوصية | `/privacy` |
| Refund & Cancellation Policy · سياسة الاسترداد والإلغاء | `/refund-policy` |

- Text: `frontend/src/features/legal/documents.ts`, Arabic and English side by side; the
  page layout is `LegalPage.tsx`. Keep them true to how Mizan works (no automatic
  renewal, no trackers, the providers actually used) and, when they change, update
  `BUSINESS.effective`.
- **The seller's details** (name, city, phone/WhatsApp) live only in
  `frontend/src/features/legal/business.ts` and are used by the legal pages, the footer,
  the contact page and the About page. Paymob checks them against the merchant account.
- Linked from the footer, the signup form ("by creating an account you agree…") and the
  owner panel's pay dialog (terms and refund policy).
- The contact form has no mailbox behind it: it opens WhatsApp with the message written out.

## The developer platform (ADR-007 D6)

`frontend/src/features/developers/`, served at the root of `dev.*` hosts and under `/dev`
elsewhere (`paths.ts`). **English by default**, Arabic on request: its own language choice
(`mizan.dev_locale`), so the website keeps its Arabic default.

- `DevHome.tsx`: what developers can build (whole activities, modules, themes) and where to start.
- `AuthPage.tsx`, `PortalShell.tsx`, `TeamsPage.tsx`, `TeamPage.tsx`, `TokensPage.tsx`,
  `AccountPage.tsx`: the portal (developer accounts, teams and members, signing keys with
  Mizan's certificates, CLI tokens, password), over `/developers` on this API
  (`backend/website_api/routers/developers.py`; logic in `system/core/backend/app/platform/developers/`).
- `devDocs.en.ts`, `devDocs.ts`: the developer docs in English and Arabic, rendered by the docs
  components (`features/docs/`). Keep them true to the code: the validator
  (`app/framework/manifest.py`), `/ext/v1`, webhooks, the CLI (`sdk/python`).
- The SDK wheel is built into `public/sdk/` by the release workflow and served at
  `dev.allmizan.live/sdk/`.

