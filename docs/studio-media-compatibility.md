# Studio media compatibility proposal

Status: PROPOSAL. No code in this branch implements P1-P4 as policy yet; the
behaviors described as "current state" are verified in source. A policy
decision is required before any change.

## Current state (verified in source, 2026-11-25)

1. Historical/static rendering. `image` and `gallery` nodes render the `src`
   stored in the tree verbatim (`app/platform/site/render.py`:117-138) in the
   editor, in authenticated preview, and in any context that renders them
   today. Templates ship their own asset/placeholder sources.
2. Typed media. `mizan.media.experimental.v0`
   (`app/framework/storefront_values.py`): an exact `{schema, src, alt}`
   envelope. `src` must be tenant-scoped product-image storage
   (`*.public.blob.vercel-storage.com/t/<tenant>/product_image/...` or
   `/uploads/t/<tenant>/product_image/...`), with no credentials, query or
   fragment, and an allowlisted extension. The provider never fetches the
   URL, so validation cannot become a server-side request.
3. Consented card path (`inventory/storefront/cards.py`): a product image
   surfaces only when the owner explicitly set `show_image` for that product,
   AND the exact URL matches a `WorkspaceFile` row of kind `product_image`
   owned by that product with an allowlisted content type. Any mismatch is
   `SourceUnavailable`: the row fails closed and nothing renders.
4. Public synthetic scope: any absolute off-host URL anywhere in a tree,
   including image sources and including the reviewed tenant blob URLs,
   refuses publish and make-public with a readable 422
   (`synthetic_scope_violations`). `allow_connected_data` stays false;
   connected-data public rendering is refused outright.
5. The synthetic visitor CSP is `img-src 'self' https:`; the scope check in
   (4) is stricter than the CSP and is the enforcing layer.

## Review boundary (constraints as given)

- Preserving an image already rendered in its existing context does not
  authorize newly exposing a stored ERP `image_url` through a public binding.
- A provenance flag is not validation or consent.
- No unrestricted legacy-url bypass to new bindings.
- Retain the current matching workspace-file checks and the public
  connected-data refusal.
- Distinguish unchanged historical rendering from new binding resolution /
  public exposure; no silent migration; no new external image requests.

## Proposal

P1. Historical static sources: unchanged. Stored trees are never rewritten
    (no migration, silent or otherwise). Image and gallery nodes keep
    rendering exactly where they render today. No new server-side fetching
    is introduced for them; they remain browser-side `<img>` loads, as today.

P2. Public activation: unchanged. Off-host absolute URLs, including tenant
    blob-storage URLs, keep refusing publish and make-public in synthetic
    scope with readable 422s. Nothing here weakens `_off_host_urls`.

P3. New binding resolution into image content: any value a binding, card or
    repeat path writes into an image `src` must be a typed
    `mizan.media.experimental.v0` value that passes `check_media` INCLUDING
    the `WorkspaceFile` ownership and content-type match, in the same
    projection path that writes it. Raw strings, legacy URLs, provenance
    flags, and "already rendered elsewhere" claims are not accepted. A path
    that cannot validate fails closed (`SourceUnavailable`; the row hides
    under the existing zero-row behavior).

P4. Deferred option, NOT part of this ask: a same-host media route on the
    visitor host that serves only validated tenant product images, so
    consented product imagery could appear on public synthetic pages without
    off-host references. Until such a route exists and is separately
    approved, product imagery stays off public synthetic pages even when
    consented for authenticated contexts.

## Non-goals

- No silent migration or rewriting of stored trees.
- No server-side fetching, normalization or proxying of arbitrary external
  image URLs.
- No change to the public connected-data refusal or to
  `allow_connected_data = false`.
- No general legacy-URL allowlist or bypass flag.

## Money note (from the same review)

Reuse `storefront_values.money_value` for any price the next provider slice
exposes: explicit currency from the owner's consent record, canonical
two-place decimal text. The two-decimal limitation is a reviewed bound, not
general currency-scale correctness; claims must not exceed it.

## Decision requested

Approve P1-P3 as the standing media boundary. P4 may stay deferred
indefinitely; it needs its own explicit approval if ever wanted.
