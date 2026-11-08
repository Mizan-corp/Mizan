---
name: code-review
description: Procedure for conducting rigorous code review in Mizan
---

# Code Review Procedure

Before committing or pushing code:

1. **Architecture & Boundaries:**
   - Did this change leak private module details across domain boundaries?
   - Is tenant isolation maintained?

2. **Types & Quality:**
   - Are there any remaining TypeScript errors or uninspected warnings?
   - Run `npx tsc -b --noEmit` to verify.

3. **Performance & Security:**
   - Are database queries indexed?
   - Are inputs validated using Pydantic?
   - Is clinical data isolated from administrative views?

4. **Change Impact Report:**
   - List all modified files.
   - Detail any shared components touched and affected downstream routes.
