# ADR-004: Owner Accounts, the Owner Panel and Paymob

## Status
Accepted (2026-11-09)

## Context
Every login belonged to exactly one workspace. A business owner with two branches or two
businesses had two unrelated logins and no single place to see them. Subscribing happened
inside the ERP, where any signed-in user could reach a "simulate payment" endpoint and give
their workspace a paid plan for free, and the payment webhook accepted unsigned requests.

## Decision
- **Owner accounts.** A new `owner_accounts` table (login, name, phone, email, password).
  `tenants.owner_account_id` says who owns a workspace; `users.owner_account_id` marks the
  ERP user the owner signs in as there. Migration `v47_owner_accounts` backfills one owner
  account per existing workspace from its first admin, reusing that admin's username and
  password. Signup, the admin panel's "New workspace" and the bootstrap create one too.
- **Where you sign in decides who you are.** The app's `/login` (no workspace in the
  address) is the owners' sign-in: it authenticates an owner account (`POST /account/login`
  on the system API), issues a token with `scope: owner` and hands it to the owner panel,
  which has no sign-in page of its own. A workspace's login page (`/c/<workspace>/login`)
  authenticates an ERP user; employees who try `/login` are sent there. The website keeps
  its own copy of the owner session (signup, and `/login` passing through its `/session`)
  so it can offer "back to your panel" and "sign out"; signing out anywhere clears both. The ERP refuses owner tokens; the owner API
  refuses ERP tokens. "Open workspace" issues an ERP token for the owner's user in that
  workspace and hands it over in the URL fragment, like ADR-003's handoffs.
- **A fourth product, `owner/`.** Arabic RTL frontend and `owner-api`, on their own domains
  (`mizan-co-owner`, `mizan-co-owner-api`). After signup the website hands the new owner to the panel, where a
  short interactive tour introduces it.
- **Paying happens only in the owner panel, through Paymob.** Checkout creates an invoice
  and a Paymob intention (`POST /v1/intention/`), then sends the owner to Unified
  Checkout. Paymob's transaction callback is verified with HMAC-SHA512 over Paymob's
  documented field list (constant-time compare), recorded once in `payment_transactions`
  (unique `event_key` = transaction id + state), matched to the invoice by its reference,
  and checked against the invoice amount before `activate_invoice` runs. The return page
  never trusts the redirect's query string; it waits for the invoice to turn paid.
- **The ERP's billing API is read-only.** `/billing/checkout`, `/billing/simulate-payment`
  and the unsigned `/billing/webhook` were removed.
- **Bearer before cookie.** The ERP API now prefers an explicit `Authorization` header over
  the session cookie, so a handed-over session isn't overridden by an older sign-in in the
  same browser.

## Consequences
- An owner signs in once and reaches every workspace; staff keep their per-workspace logins.
- Owner and workspace-admin passwords start equal. Changing the password in the owner panel
  updates the linked workspace users too; changing it inside one workspace doesn't change
  the owner account.
- Online payment is off until `PAYMOB_SECRET_KEY`, `PAYMOB_PUBLIC_KEY`, `PAYMOB_HMAC_SECRET`
  and `PAYMOB_INTEGRATION_IDS` are set on `mizan-owner-api`; until then checkout answers 503
  and the admin team can still mark invoices paid by hand.
- Paid periods are tracked per invoice (renewals start where the paid period ends), but a
  lapsed subscription doesn't yet move a workspace to read-only on its own.

## Email to owners (built 2026-11-14, #71, #72)

- **Signup** asks for the owner's email and phone (both required) and emails a 6-digit code to
  verify the address. The owner panel shows a banner until it is verified; existing owners add
  and verify their address there (account page). Changing the address clears the verification.
  An address can be verified on one owner account only.
- **Codes** (`owner_codes`): 6 digits, 15 minutes, single use, 5 wrong tries, at most one a minute
  and three an hour per owner and purpose; only an HMAC of the code is stored.
- **Forgot password** on the owner panel's sign-in page (system API `POST /account/password/forgot`
  and `/reset`, rate-limited, CSRF-exempt like `/account/login`): a code to the account's
  verified address only, by username or by that address; the answer is the same whether the
  account exists or not. Resetting sets the owner's and every linked workspace login's
  password, ends every session and signs the owner in.
- **The admin panel** can email an owner a reset code (verified address only) or set a
  temporary password; both now update the linked workspace logins too.
- **Receipts** are emailed (with the PDF) when a payment is applied, online or marked paid by
  the team; **reminders** go out daily (`owner_billing_reminders`): trials 3 days before and at
  the end, paid periods 7 days before and at the end. Each once (`owner_email_log`), to
  verified addresses only, cloud workspaces only.
- **Delivery**: SMTP (`EMAIL_SMTP_*`, `EMAIL_FROM`, `EMAIL_REPLY_TO`); production sends through
  Brevo's relay as `Mizan <no-reply@allmizan.live>` (domain authenticated in Brevo), replies to
  `support@allmizan.live`. Without a host, mail is only logged and the panel hides the
  verification banner; forgot password then answers 503. Locally, Mailpit catches everything
  (`docker-compose.yml`, http://localhost:8025). Phone numbers are collected, not verified
  (no SMS provider yet).
