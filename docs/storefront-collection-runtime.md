# Experimental bounded collection mechanics

Status: LOCAL ONLY. Experimental repeat envelope is now wired into local API discovery/save-validation/preview and Studio UI, not deployed. Hosted scalar dynamic bindings remain unchanged.

## Checked local slice

- Generic trusted async collection runtime. Exact text-only projection, separate stable unique key, 1 to 24 items and 1 to 12 fields. No expressions, commands, imports, URLs, prices, images, pagination or implicit first item scalar conversion.
- Immutable checked item values, bound to registry issuer, tenant, language, module and source. Current business-module activation is checked again on lookup. No cross-tenant cache.
- Actual site-owned provider reads only saved header navigation labels. The existing settings have no persisted link IDs. Unique href fingerprints survive label edits and reordering; duplicate hrefs fail closed. Changing href changes identity. This is an experimental compromise, not a new persisted identity model. Destinations and settings blobs never leave the provider. Explicit top-N selection is documented provider behavior.
- One existing heading in a column is the visual template. An internal reviewed plan expands it into ordinary native heading nodes. Settings, other-language content and source tree are retained. IDs derive deterministically from source, template and stable item key. No collection page schema exists yet.
- Complete plan/native metadata validation precedes provider calls. Maximum expanded native node count is checked conservatively before reading, and native validation plus byte limit are checked afterward. Generated-ID collisions fail closed. Mixed scalar/collection pages are explicitly refused in this local slice.
- Empty collections remove the template in the render copy. Provider errors remain errors, never stale or static success. Renderer escapes plain text normally.

## Evidence

16 local tests pass for collection contracts, active modules, tenant/language/registry item scope, immutable/copy behavior, projection failures, saved navigation source/order/limit/identity, source failures versus empty state, native expansion, deterministic IDs under reordering, settings retention, unchanged source, pre-read refusal, bounds, escaping and collision rejection.

Read-only isolated DB checks matched both current tenants' empty saved navigation lists and rejected mismatched tenant before settings reads. A separate rollback-only transaction on the throwaway owner tenant created three nonempty saved links, exercised the actual provider, expanded native headings and rendered them with the ordinary Python renderer. Exact original settings were verified after rollback. No fixture writes were committed.

Actual generated native renderer previews were opened in Chrome at desktop 1440 and mobile 390 widths, using the renderer's matching device option. Three headings and no horizontal overflow were asserted, and screenshots inspected. These are native renderer pixels, NOT Studio UI, save/reload, API authorization, public publishing, or catalog proof.

## Integrated local continuation

The persisted experimental repeat envelope, discovery, native heading-template UI, source preview verification, draft save/reload and byte-identical SDK/platform manifest validation are now implemented locally. Collection/repeat checks total 20 passing tests. The Python renderer rejects unresolved repeats even when optional validation is disabled. Dynamic public publish remains blocked with 409.

Inventory owns explicit product/category selection, default empty. Only selected active products and independently selected categories supply id/name text. Product activity alone never grants website visibility. Core owns a separate website-authored display name/tagline, never invoice/legal fallback. The Studio Data panel saves these module settings through dedicated dual-permission APIs and invalidates resolved previews after a successful change.

See core-site-reflection-scope.md for local real-owner API/UI/DB rollback proof, permission and malformed-input checks, mocked dirty/conflict/failure checks, and the module audit. Local normal-owner save/reload was enclosed by an outer transaction and restored exactly. It is not committed hosted persistence evidence.

## Remaining

Complete exact branch source checkpoint/readback/build, isolated test deployment and hosted acceptance. Money/media, general pagination, mixed scalar/repeat pages, protected shopper identity and own-record access, public dynamic rendering and commerce commands are not implemented. No benchmark completion claim.

## Composition continuation

A local composition adapter now permits scalar module-profile siblings alongside one heading-repeat template. All languages and both provider declarations validate before reads. The original static native tree remains unchanged. Same-node scalar/repeat, multiple repeat templates and expanded page bounds fail closed. Exact source and UI/DB evidence is recorded in core-site-reflection-scope.md. Earlier one-template/no-scalar restriction above describes the first hosted checkpoint, not the new local adapter. Multiple templates, arbitrary repeated card subtrees, typed prices/media and public dynamic rendering remain outside this slice.
