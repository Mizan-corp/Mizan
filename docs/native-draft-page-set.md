# First-party multi-page draft starter

24 November2026, hosted acceptance at11:55 on the isolated test site. This is a small common builder capability, not a full store template and not allwirya parity.

The Studio workspace offers Add draft page set. An explicit unused prefix produces four native editable S2 drafts: Home, Products, About and Contact. The owner previews each page first, then explicitly creates all four. The fixed first-party starter accepts no uploaded code or arbitrary trees. It changes no existing page, shared design, navigation, publication state or module data consent. Starter copy is instructional English, not facts about the owner's business. No forms/contact delivery, connected products, public runtime, checkout or Help Desk integration is included.

Backend validates the entire fixed package before inserts; tenant/slug uniqueness makes collision atomic. The caller needs site.manage. Malformed/unknown inputs fail strict422. A collision refuses409 without replacing any page. UI freezes on uncertain results and requires page-list refresh before retrying; no automatic retry. Returned identifiers, exact addresses/titles/trees and unpublished draft state must match preview before reporting success. Preview/install/cancel share an in-flight guard, and cancel is disabled during requests.

## Local evidence

- Ordinary owner login and UI preview, create4, list/reload, open Home, edit text, save and fullreload pass against actual API/models with an outer rollback. Existing Studio page and shared website settings are exact after rollback. No committed starter pages remain.
- Anonymous401, strict malformed422, pre-existing one-of-four collision409 with zero other pages created, exact duplicate409 with state unchanged pass.
- Independent PostgreSQL transactions on a disposable schema: same-prefix concurrency creates4once and409once; separate tenants may use same prefix without seeing each other's pages; forcedRLS hides foreign pages; injected third-page failure leaves zero partial pages. Schema removed.
- Studio116tests pass/1skip, TypeScript and static Studio build pass. Desktop preview and edited390px mobile canvas pixels inspected with no overflow. Physical-mobile authoring and screen-reader acceptance not claimed.

## Gates and next work

Source checkpoint eeb5da03e75e4220a1d7a39d44d463605af10a42 passed exact9file readback. Hosted deployment dpl_EJcJaM7Mtug98D37GDoZqyoVuk3b is now canonical at https://mizan-studio-feature-test.vercel.app/studio-preview.html . Hosted ordinary owner session previewed/created4drafts, list/reloaded, opened/edited/saved/fullreloaded Home and passed mobile390 no overflow. Duplicate install409 preserved exact state. Existing pages/shared appearance remained exact; only4known unpublished fixture drafts were deleted and absence verified. No revisions or published trees were created. Temporary credentials deleted. Protected candidate responses/assets were forwarded through authenticated transport; no local substitute API. The accepted ERP bundle remains byte-identical to the preceding shared worksheet release. This is not a reason to relax public dynamic publication guards. After this slice, shared navigation/design/template application, typed package/SDK/update contracts, owned media delivery and functional common actions remain distinct unfinished common work. Activity-specific business workflows are deferred to the user's later activity-by-activity review.
