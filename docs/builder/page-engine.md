# The page-engine contract

## Status

Proposed 2026-11-23. Working contract for ADR-015 step S2, not yet accepted architecture.

The concrete shape of ADR-015's page engine (step S2) and the SDK round-trip (ADR-016 D4),
pinned before code. When the implementation and this file disagree, the file wins until the
ADR changes it.

## What a page is

A page is a JSON tree. Every node:

```json
{
  "id": "n_k3j9x2",
  "type": "columns",
  "settings": {
    "desktop": { "visible": true, "padding": "m", "gap": "l" },
    "tablet":  { "visible": true },
    "mobile":  { "visible": true, "stack": true }
  },
  "content": { "ar": {}, "en": {} },
  "children": []
}
```

- `id` is stable within the page (generated once, never recycled): revisions, the studio's
  layers tree and anchors point at it.
- `type` is a block id from the registry below. Unknown ids fail validation.
- `settings` is per device (`desktop`, `tablet`, `mobile`): visibility, spacing tokens, size
  and layout options. Only keys the block's schema declares; anything else is rejected.
- `content` is keyed by language code (`ar`, `en` first; any number later, ADR-015 D7). Only
  fields the block's content schema declares.
- `children` exists on layout blocks only.

## The tree levels

`section → columns → column → blocks`, drag to reorder, per-device settings on every level
(ADR-015 D4). One `canvas` section per page may position its blocks freely, with its own
mobile arrangement; the rest of the page stays responsive. Reusable sections and global
blocks are nodes referenced by id, edited once, shown everywhere they are placed.

## Block registry v0

| Block | Category | Notes |
|---|---|---|
| `section` | layout | full-width band; background, spacing, per-device visibility |
| `columns` / `column` | layout | 1–6 columns; widths per device |
| `canvas` | layout | free positioning; one per page |
| `heading` | basic | level, align |
| `text` | basic | rich text, sanitised |
| `image` | basic | from the media library; alt per language |
| `gallery` | basic | grid or slider |
| `video_embed` | basic | allow-listed hosts only (YouTube, Google Maps embeds as in ADR-015 D2) |
| `button` | basic | link, style from global styles |
| `icon_list` | basic | Lucide icons |
| `spacer`, `divider` | basic | |
| `html` | advanced | sanitised: no scripts, no event handlers, no `javascript:` URLs, no iframes outside the allow list |

Later, in their ADR-015 steps: `form` (S3+), commerce blocks (S4), activity blocks (S7),
developer blocks (S5, sandboxed). Each block declares: `id`, `version`, `category`, a typed
settings schema (with per-device flags), a translatable content schema, and default styles.
The registry is data, versioned, and shared with the SDK byte for byte.

## Storage and revisions

Tenant-scoped, RLS-protected tables: `site_pages` (id, slug, titles per language, draft tree,
published tree, status) and `site_page_revisions` (immutable snapshots). Publish copies the
draft to the published tree, writes a revision and purges the edge cache; rollback copies a
revision into the draft. Autosave writes the draft only; nothing reaches the public site
until publish. Scheduled publishing comes later.

## Rendering

The server renders the published tree plus the theme to HTML (theme templates in a sandboxed
Jinja2 environment, ADR-015 D6); a small site runtime handles interactive blocks (cart,
variant picker, filters, sliders) and is the only script the site's CSP allows besides
declared integrations. Pages are cached at Cloudflare's edge and purged on publish and on
catalogue changes. The studio previews through the same renderer (ADR-015 D6).

## The SDK round trip

The JSON above is exactly what the API stores, exactly what `mizan site-theme` packages, and
exactly what the studio imports and exports. One validator in `app/framework/manifest.py`,
copied byte for byte into the SDK; the drift test already used for manifests covers it
(ADR-016 D4).

## SEO

Per-page and per-language title and description, canonical URLs, `hreflang`, clean slugs,
sitemap and robots, Open Graph; product structured data with the shop (S4).
