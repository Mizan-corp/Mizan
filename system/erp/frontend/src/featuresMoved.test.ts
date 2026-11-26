// Step 8a: business pages live in their module, not in src/features.
import { existsSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = __dirname;
const MOVED: Record<string, string> = {
  "activities/general/modules/contacts/screens/CustomersPage.tsx": "features/customers",
  "activities/general/modules/purchases/screens/SuppliersPage.tsx": "features/suppliers",
  "activities/general/modules/inventory/screens/ProductsPage.tsx": "features/products",
  "activities/general/modules/helpdesk/screens/HelpdeskPage.tsx": "features/helpdesk",
  "activities/general/modules/operations/screens/OperationsPage.tsx": "features/operations",
  "activities/general/modules/reporting/screens/ReportsPage.tsx": "features/reports",
  "activities/general/modules/documents/screens/ArchivePage.tsx": "features/archive",
};

describe("business pages are in their module", () => {
  for (const [page, oldDir] of Object.entries(MOVED)) {
    it(`${page}`, () => {
      expect(existsSync(join(SRC, page))).toBe(true);
      expect(existsSync(join(SRC, oldDir))).toBe(false);
    });
  }
});
