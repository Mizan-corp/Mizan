# archive

The document archive (/archive): `router.py`. Listing, reading and deleting need `archive`;
`doc_type` is one of the document types and `from_date`/`to_date` are dates (whole days in the
workspace's time zone). Archived documents print at `/print/archive/{id}` (`archive`, and the branch
the document names).

Document numbers (`numbering.py`): `next_number(db, "INV")` gives the bound workspace's next
`INV-000123`. Each workspace counts each kind of document on its own (`doc_counters`, one row per
workspace and prefix, taken under a row lock in the caller's transaction); a workspace's first
number of a kind follows the highest it already used (from the global sequence of before, or the
demo data). Used for sales invoices (`INV`), returns (`RET`), quotations (`QUO`), drafts (`DRF`)
and safe deposits (`DEP`).
