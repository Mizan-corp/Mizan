# Studio website binding — acceptance playbook (English)

Status: living checklist for the storefront binding/card/repeat feature set on
`feat/studio-render-parity`. Each row says what is proven, by what evidence,
and what is explicitly NOT proven. Do not upgrade a row without the evidence
named in it.

## How to run the suites

- Offline unit suites (pure stdlib, no DB, system python3 OK):
  `cd shared/backend/tests && python3 <file>.py`
  Files: test_storefront_runtime, test_storefront_bindings,
  test_collection_repeats, test_collection_card_repeats,
  test_collection_typed_fields, test_collection_projection,
  test_scalar_binding_gate.
- Integration checks (mocked DB, real models/SQL): these need Python >= 3.11
  (`enum.StrEnum` in app models). Use the project venv:
  `/tmp/mizan-venv/bin/python <file>.py`
  Files: core_site_provider_integration_check,
  collection_provider_integration_check, card_provider_integration_check,
  card_runtime_integration_check, card_writer_integration_check,
  multi_card_runtime_integration_check.
- test_card_consent_revocation: same venv plus env and path:
  `DATABASE_URL='postgresql+asyncpg://u:u@127.0.0.1/u' SECRET_KEY='offline-test' PYTHONPATH=.. /tmp/mizan-venv/bin/python test_card_consent_revocation.py`
- Frontend: `cd system/frontend && npx vitest run` (226 pass, 1 skipped as of
  f7e368a) and `npx tsc --noEmit`.
- `python3 -m unittest discover` from the tests directory shows import errors
  for DB-backed modules (wrong cwd, missing env) — that is a runner invocation
  quirk, not a suite verdict. Run the files as above and report per-file.

Honesty rule (standing): integration checks use real models and real SQL with a
mocked session. Call them "real models/statements, mocked session", never
"DB integration".

## Current acceptance matrix (2026-11-25)

| Capability | State | Evidence |
| --- | --- | --- |
| v0 heading binding + repeat (en/ar) | Proven offline | test_storefront_bindings, test_collection_repeats |
| v1 typed card repeat (name/price/image slots) | Proven offline + live browser (name+price) | test_collection_card_repeats, nativeCardRepeats.test.ts; live proof below |
| Zero-grant privacy (repeat pruned empty) | Proven live | 2026-11-25: zero consent, preview rendered empty, reload persistence verified |
| Positive price expansion (EGP, 2 products) | Proven live | 2026-11-25: in-editor + signed-in private preview pixels, two cards with real fixture names/prices |
| Image slot expansion | NOT PROVEN | Uploads refused by design on the test host (no BLOB_READ_WRITE_TOKEN); no WorkspaceFile product_image can be created via UI. See deploy/studio-test/README.md |
| Consent-intersection revocation (drop-out) | User-approved 2026-11-24 15:03, proven offline | test_card_consent_revocation, multi_card check |
| Scalar (individual element) binding of module data | REFUSED by design, gate pinned | test_scalar_binding_gate: collection contracts cannot register as scalar providers; v1 consent wording names cards/repeating lists only — a fresh explicit opt-in version is required before any implementation unlocks scalar fields |
| Static synthetic visitor page (public) | Live after 8217f02 | 200 when enabled, app-404 when disabled |
| Dynamic connected-data repeats (public) | Do not exist | Authenticated signed-in draft preview only; no public dynamic publishing, no checkout |

## Live-proof protocol (fixture-owned, reversible)

1. Synthetic fixtures only ("Fixture …" names), created via UI. Verify fixture
   identity before any opt-in. No real products, no real consent grants by the
   agent.
2. Opt in via the real UI with the bilingual confirm; capture wording.
3. Prove with pixels (screenshot the rendered preview), not API responses.
4. Restore in the same run: remove bindings/repeats, save; consent back to the
   exact prior effective values (verify by authenticated GET); catalog
   selection back to empty; deactivate fixture products.
5. Record edit_token/metadata deltas explicitly — restore means effective
   values, not exact database restoration. No direct DB cleanup.
6. Record the site outcome and release the browser lease.
