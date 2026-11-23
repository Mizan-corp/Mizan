# ADR-016: UI profiles, and the builder as a full web app

## Status

Proposed 2026-11-23. Owner direction (2026-11-23): start the SDK and builder foundation now,
document the work as it lands, and treat the builder as a whole web interface, not a settings
screen. Extends ADR-015 (the website builder and site themes) and ADR-010 (theme packs). Work
happens on a branch; nothing deploys until merged and released in the usual way (ADR-011).

## Context

The architecture review of 2026-11-23 measured the platform against the owner's goal: compose
websites and ERP systems from changeable, reusable pieces (layouts, colours, animations,
themes, shapes, pages), with changes organised as profiles instead of scattered edits. It found:

- the SDK describes data (entities, screens, themes, activities), not UI: it cannot express a
  page, a layout or an animation;
- theme packs are one token set per workspace: colours, fonts, radius, shadows, one of three
  motion presets, density (ADR-010 D3). A module cannot carry its own look;
- the screen builder edits role home, menus, dashboards, form layouts and custom fields only
  (ADR-006 phase 5, `app/framework/layouts.py`);
- the website builder of ADR-015 is specified, and only its protective step S0 is done (#156).

What exists to build on: theme packs (`.mzm`, kind `theme`), the designer's saved layouts,
activity packages, and the validator shared with the SDK byte for byte (ADR-007 D6).

## Decision

### D1. One resolution order for everything visible

```
platform defaults → activity → variant → theme pack → workspace profile → role layout → device preference
```

ADR-006 D2's "module → variant → workspace settings, custom fields, role screens" gains the
profile layer. A module can carry a look through its activity and through profiles, not only
through code. Every visible value resolves down this chain; nothing reaches for a sibling.

### D2. UI profiles are a package

A UI profile extends the theme-pack format with layout recipes: per module or screen, the
arrangement, density, widgets and motion preset. New package kind `ui_profile`, signed and
installed like a theme, one active per workspace. "Save as profile" in the designer exports
the workspace's current look as a profile draft; the SDK checks and packages it
(`mizan profile new|check|package`). Paid profiles wait for the marketplace (#65, #105), like
paid themes. A profile never carries content or data: it is look and arrangement only, so
applying one is always safe to undo.

### D3. The builder is a full web app

The studio of ADR-015 D1 is a full-screen app at `/admin/studio`, not a settings screen: page
list, editing canvas, per-device preview, global styles, a layers tree, reusable sections and
global blocks, undo/redo, autosave drafts, revisions and publish. The same page engine later
renders custom ERP pages and dashboards, so the platform grows one engine, not two builders.

### D4. The SDK is the contract

Everything the studio and the designer can do must round-trip through SDK files: the page tree
(JSON), site themes (ADR-015 D5, kind `site_theme`), UI profiles (D2) and block declarations.
The platform and the CLI share one validator, kept identical byte for byte, as manifests
already work (ADR-007 D6). If a change cannot be expressed in the SDK, the feature is not done.

### D5. Security rules are unchanged

Workspace users build pages from blocks; custom CSS is sanitised, no custom JavaScript
(ADR-015 D2). Developer blocks with sandboxed JavaScript stay at ADR-015 S5, after the shop
works end to end. Profiles and site themes pass the same validation as theme packs: known
tokens, safe colour formats, readable contrast (ADR-010 D3).

### D6. Order of work

1. This ADR and the page-engine contract (`docs/builder/page-engine.md`): the page-tree schema
   and the first block registry, before any code.
2. ADR-015 S1: ERP to `/admin`, HttpOnly cookie sessions, strict CSP. Hardens every workspace.
3. ADR-015 S2: the page engine (tree storage, block registry, server renderer, edge caching).
4. The studio shell (ADR-015 S3): the builder's full web interface (D3).
5. UI profiles across ERP modules (D2), then ADR-015 S4–S7 as specified.

## Consequences

- The builder's interface is a product surface of its own, designed and tested like the ERP,
  not a form in settings.
- A workspace's look becomes portable: between workspaces, between the owner and the
  marketplace, and between the UI and the SDK.
- Two more package kinds mean the validator, the CLI and the module centre grow together; the
  byte-copy test keeps them in step.

## Open questions

- Who the studio serves first: Mizan's team building sites for clients, workspaces
  self-serving, or developers selling site themes (asked 2026-11-23).
- Whether pixel-perfect reproduction of arbitrary sites is a hard requirement, or the staged
  block model (blocks now, developer blocks at S5) is enough (asked 2026-11-23).
- Module-level themes: picked by businesses inside the app (a new capability), or shipped by
  developers in packages (half exists as code-level variants today).
- ADR-015's own Q1–Q6 stay open for their steps.
