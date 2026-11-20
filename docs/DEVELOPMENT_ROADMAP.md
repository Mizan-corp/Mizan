# Mizan ERP — Development Roadmap

The working plan, in priority order, is [`TASKS.md`](../TASKS.md); every open item is a
[GitHub issue](https://github.com/mizan-corp/Mizan/issues). This page is the long view.

## Done
- **Platform:** multi-tenancy with row-level security; one permission system with acting roles
  (ADR-006 phase 3); modules, activities and variants as data, screens and menus as data, the
  screen builder (ADR-006 phases 1–5); four separate products on one domain (ADR-003, ADR-008);
  owner accounts with many workspaces (ADR-004); releases by CI with migrations (#64).
- **On site (ADR-005):** single-device and LAN installs, signed licences bound to one computer,
  updates with rollback, local backups, the network page.
- **Developer platform (ADR-007):** declarative community modules installed from signed files with
  scope approval, `/ext/v1`, signed webhooks, the developer portal and docs at dev.allmizan.live
  (English by default), the `mizan` CLI.
- **Activities and themes (ADR-010):** every activity is one self-contained folder; theme packs
  (one per workspace, chosen by its admin); activity packages for developers, checked and signed.

## Next
1. **Getting paid** (waits on Paymob's production keys): live payments, then reconciliation,
   plan changes, receipts, and the marketplace for paid modules and themes (#65, #105).
2. **The global Mizan**: the shared platform and the `general` modules every workspace uses
   (POS, sales, inventory, purchases, finance and accounting, HR, reports, settings).
3. **Changing a workspace's activity** (#107), which also runs developers' activity packages.
4. **Activities, one by one** (owner's decision, 2026-11-12): restaurant, pharmacy, healthcare,
   hotel and the others, each brought to the depth of retail.
5. **Egyptian Tax Authority e-invoicing and e-receipts** (waits on test credentials and the
   signing decision).
6. **Own servers**: moving from Vercel to Mizan's own cluster, which brings code modules in
   isolated containers (ADR-007).

## Healthcare activity (its own track, when its turn comes)
The healthcare requirements (HLT-01 … HLT-24) are in
[`PRODUCT_REQUIREMENTS.md`](PRODUCT_REQUIREMENTS.md) and the SRS
([`developer/mizan/srs/SRS-Mizan-v1.0.md`](developer/mizan/srs/SRS-Mizan-v1.0.md)); its modules
are laid out in `activities/healthcare/modules/`, most as planned or scaffolded.
