# Mizan Website

The public face of Mizan: landing, product, industries, pricing, blog, the docs portal,
self-serve signup with the 3-step onboarding wizard, contact, and the legal pages.

| | Folder | Local | Production |
|---|---|---|---|
| Frontend | `frontend/` | `npm run dev:website` → http://localhost:5174 | https://mizan-co.vercel.app |
| API | `backend/` | `docker compose up website-api` → :8001 | https://mizan-co-web-api.vercel.app |

- The API exposes only `GET /platform/plans` and `POST /platform/signup` (rate-limited).
  Signup creates the owner account and workspace, seeds sector demo data and returns a token.
- After onboarding the new owner lands in the **owner panel**, already signed in
  (`openWithSession` in `shared/frontend/src/lib/handoff.ts`).
- "Sign in" goes to the system app's `/login`, which sends owners back through `/session`
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
