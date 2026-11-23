# Full test-service extension

Test only. Positive owner/platform-admin acceptance remains incomplete.

The existing Studio/ERP package can be extended with the real owner_api, admin_api and website_api source trees plus their normal auth, CSRF and session dependencies. No special test auth bypass, account elevation or DB schema operation is included.

1. Build frontends with build-frontends.py and the existing isolated origin. It overrides production app/API URLs without editing production env files.
2. Preserve website SessionRoutes.tsx base-aware session pathname change. Owner login passes through /website/session and returns to /owner/. This was checked offline with a noncredential fixture, not a real owner token.
3. Run package-control-plane.py with --base-package, --service-source (repository root containing owner/backend, admin/backend, website/backend), --frontend-builds and a fresh --output. It excludes environment/private CLI metadata and preserves the original Studio/ERP entry bytes.
4. Review the candidate, then deploy only to the established isolated test project. A protected no-alias candidate can be checked before promotion. Do not relax deployment protection.

## Recorded live checkpoint, 2026-11-24 00:47 Cairo

Deployment dpl_9Q3dhzrRLgxs6FbAGiTXC9MKbUJB is READY and promoted in mizan-studio-feature-test. The existing root Studio and ERP products page were reloaded and visually checked. Owner /owner/login and admin /admin/ sign-in pages visually checked. Website /website/session app entry serves200.

System, owner, admin and website health endpoints report200/database connected. No-credential owner profile, admin overview and developer profile return401. Existing tenant-admin session is refused by owner profile401 and platform-admin overview403. Owner/platform-staff positive acceptance and distinct-tenant checks are still open.

No signup, role grant, billing, checkout, email, licence or other control-plane mutation was tested. The website signup source creates owner/workspace and attempts verification email. Hosting metadata listed only hidden DATABASE_URL and SECRET_KEY names in the isolated environment. Do not introduce production payment/email credentials.

## Developer documentation references

Website developer docs retain production SDK download and ext/v1 examples as reference text/code samples. They are not automatic authenticated requests and were not executed. Developer portal navigation uses the isolated test override. The SDK wheel is not included in this candidate. Do not claim SDK download/install acceptance or ask people to execute those production examples as part of the test. Some descriptive docs still name the normal developer host.

## Recovery

Previous Studio/ERP-only deployment dpl_FKwr7EWS5kXc3QEQEu1NgdpdfYws is the rollback reference. Never deploy a bundle whose ERP API defaults to the external production API. The base packager checks for that error. The extension guard rejects production Mizan URLs in owner/admin execution bundles. Website documentation references are intentionally classified separately, not silently removed.

This recipe does not recreate DB bootstrap or secrets, does not establish test owner/staff identity, and does not prove full product readiness.
