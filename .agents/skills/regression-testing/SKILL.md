---
name: regression-testing
description: Procedure for verifying that existing features remain intact across Mizan
---

# Regression Testing Procedure

1. **Compilation Check:**
   - Execute `cd frontend && npx tsc -b --noEmit`.
   - Verify exit code is 0.

2. **Bundle Build Check:**
   - Execute `cd frontend && npm run build`.
   - Verify all chunks build without syntax or rollup errors.

3. **Core Route Verification:**
   - Verify authentication flow (`/login`, `/signup`).
   - Verify tenant workspace resolution (`/c/:slug/*`).
   - Verify active sector routes (`/clinic`, `/pos`, `/inventory`, `/finance`).

4. **Visual Browser Inspection:**
   - Use Playwright MCP to visit key pages.
   - Verify layout is stable with no broken layout boxes or displaced headers.
