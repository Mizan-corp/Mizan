# S2 page engine: experimental partial implementation

## Status

Proposed 2026-11-23. **INCOMPLETE, NOT READY TO MERGE OR DEPLOY.** This branch is a partial
implementation of ADR-015 S2, not a completed page engine or the studio web interface.
ADR-016 and page-engine.md remain Proposed. This note records the supported subset rather
than changing the ADR roadmap.

## Implemented subset

- `shared/backend/app/framework/manifest.py`: version-1 block registry and `page_problems()`.
  `sdk/python/mizan_sdk/manifest.py` is the byte-identical copy. The SDK drift test checks bytes.
- `shared/backend/app/platform/site/render.py`: fixed platform block rendering, escaped text,
  HTML5 parser sanitization through pinned `nh3`, and a fixed sandboxed Jinja2 document wrapper.
  No user-supplied theme templates or JavaScript execute here.
- `system/backend/tests/test_site_pages.py` and `sdk/python/tests/test_pagetree.py`: focused
  validator, sanitizer, URL, rendering, metadata and byte-copy tests. No database required.
- `shared/backend/pyproject.toml`: declares `jinja2==3.1.6` and `nh3==0.3.2` for the renderer.

## Supported data and rendering

The root is one section. It contains columns containers or at most one canvas; columns hold
one to six column nodes, columns/canvas hold basic blocks. Node ids are unique. The current
schema constrains spacing, alignment, widths, backgrounds and sizes to enum tokens, not raw
CSS. Content keys are language codes; content fields follow the registry. The validator caps
nodes and depth. It does not yet provide reusable references or enforce required content for
each language. Empty content renders an empty block or no media/link.

Rendering selects a device explicitly, merging that device's settings over desktop. It is
not automatic responsive device detection, and a pre-rendered desktop document does not
switch to the mobile tree when resized. CSS covers the supported tokens and grid columns;
galleries support a grid or CSS scroll-snap strip. Icon lists currently fall back to text
bullets, not loaded Lucide glyphs. Canvas children currently flow in a flex container, not
free-positioned coordinates. A real canvas arrangement remains unimplemented.

Image/link URLs reject protocol-relative paths, backslashes, controls, credentials, raw quote
or markup characters, and unexpected ports. Images permit http(s) URLs or site paths. Links
also permit mailto, tel and anchors. Embeds permit HTTPS default-port YouTube embed paths and
Google Maps embed paths only. No URL fetching or media-library ownership check occurs here.
External URLs can still disclose visitor request metadata when loaded; this is not a privacy
or SSRF certification.

Rich text uses `nh3` with an explicit tag/attribute/scheme allow list. Advanced HTML adds
structural tags, images and tables, but no CSS, event attributes, frames, SVG or MathML.
Provider frames are emitted only by the dedicated embed block. This is intentionally narrower
than the eventual ADR HTML feature. Palette output accepts only five known color tokens with
six-digit hex values. Rich color expressions and custom CSS are unsupported in this slice.

The document includes escaped title/description, canonical and Open Graph metadata. `alternates`
is a language-to-URL map: no alternate URL is invented from a canonical. A caller must supply
correct absolute production URLs. Sitemap, robots and route-level SEO are not implemented.

## Remaining S2 work

- Tenant models, migration, immutable revisions, RLS and cross-tenant tests.
- Authenticated draft/save/publish/rollback API and public published-only routes.
- Site service integration, CSP response headers, caching and purge hooks.
- Full page collections, header/footer composition, languages and shared references.
- Theme template validation and supported sandbox context. The fixed Jinja2 wrapper is not a
  theme system. Nothing in this branch changes S2 requirements or defers them by assertion.
- Full supported-setting semantics, free-positioned canvas and preview/device integration.
- Adversarial browser testing and integration tests under the real site's CSP/session model.

Studio editing, autosave, undo/redo and publish UI remain S3. No studio web app exists on this
branch. No production server or existing runner checkout was changed.

## Verification scope

Focused platform and SDK tests run in a standalone repository-layout fixture, using real
manifest.py and the changed files. This avoids the backend conftest/database fixtures, so it
is not a full backend-suite or full-monorepo run. CI's selected Ruff rules are checked on
changed Python files. The repository targets Python 3.12; the local fixture uses Python 3.10.
The complete dependency install, database tests, packaging, real HTTP CSP and production
integration remain unverified.

Arabic desktop/mobile renderer fixtures were captured in Chrome and visually inspected:
two-column hero and gallery on desktop; stacked hero and a hidden gallery on mobile. All
media in those screenshots is a local illustration labeled RENDERER FIXTURE. They are
renderer evidence, not screenshots of the studio UI, and are not deployed site pages.
