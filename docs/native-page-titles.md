# Native unpublished-page titles

Status: isolated Studio feature slice, not full builder or storefront readiness.

Click the title at the top of an unpublished native page. Enter a title for the language selected when the form opened, choose Use title, then Save changes. Cancel leaves the staged title unchanged. The 1 to 120-character title does not change the page heading, address, native tree or other title languages. Canvas Undo/Redo does not edit titles. Save is disabled while the title form is open to prevent silently ignoring typed input.

The existing draft API receives the exact native tree, complete title map and optimistic edit token. A mismatching response cannot be treated as verified. A 409 freezes saves and retains local changes; the recovery export includes both titles and tree. Leave/switch warnings count title-only changes. Returning home refreshes metadata rather than retaining stale page cards.

Published pages cannot be renamed here: current storage shares one title map between draft and published versions. No new claim about published metadata isolation is made. There is no slug editor, deletion, publication or migration.

Local unit, type, build and actual desktop1440/mobile390 mocked-API interaction checks cover title validation, title-only dirty state, language preservation, tree preservation, save/reload and conflict refusal. Real isolated API with local frontend verified UI rename/save/reload/home against an existing throwaway unpublished acceptance page. That is not hosted frontend proof. Hosted proof must be recorded separately after deployment. Fixture content is retained.
