// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import {
  SECTOR_OPTIONS,
  SECTOR_MODULES_MAP,
  SECTOR_PRIMARY_ROUTES,
  getSectorModules,
  getSectorDefaultFeatures,
} from "../plans";

describe("Sector and Module Mapping (Anti-Regression)", () => {
  it("healthcare sector loads only medical and clinic modules", () => {
    const modules = getSectorModules("healthcare");
    const moduleIds = modules.map((m) => m.id);

    // Must include domain-specific healthcare modules
    expect(moduleIds).toContain("healthcare_clinic");
    expect(moduleIds).toContain("appointments");
    expect(moduleIds).toContain("prescriptions");
    expect(moduleIds).toContain("insurance_claims");
    expect(moduleIds).toContain("lab_orders");
    expect(moduleIds).toContain("inpatient_beds");

    // Must NEVER include cross-sector irrelevant modules
    expect(moduleIds).not.toContain("recipe_bom");
    expect(moduleIds).not.toContain("kitchen_kds");
    expect(moduleIds).not.toContain("tuition_fees");
    expect(moduleIds).not.toContain("school_buses");
  });

  it("restaurant sector loads dining, KDS and recipe BOM", () => {
    const modules = getSectorModules("restaurant");
    const moduleIds = modules.map((m) => m.id);

    expect(moduleIds).toContain("restaurant");
    expect(moduleIds).toContain("kitchen_kds");
    expect(moduleIds).toContain("recipe_bom");
    expect(moduleIds).not.toContain("healthcare_clinic");
    expect(moduleIds).not.toContain("tuition_fees");
  });

  it("school sector loads student affairs and tuition fees", () => {
    const modules = getSectorModules("school");
    const moduleIds = modules.map((m) => m.id);

    expect(moduleIds).toContain("school");
    expect(moduleIds).toContain("tuition_fees");
    expect(moduleIds).toContain("school_buses");
    expect(moduleIds).not.toContain("healthcare_clinic");
    expect(moduleIds).not.toContain("recipe_bom");
  });

  it("pharmacy sector loads FEFO expiry and INN alternatives", () => {
    const modules = getSectorModules("pharmacy");
    const moduleIds = modules.map((m) => m.id);

    expect(moduleIds).toContain("pharmacy");
    expect(moduleIds).toContain("fefo_expiry");
    expect(moduleIds).toContain("inn_alternatives");
    expect(moduleIds).not.toContain("tuition_fees");
  });

  it("all defined sectors have corresponding primary routes and modules", () => {
    for (const sector of SECTOR_OPTIONS) {
      const sectorKey = sector.value;
      expect(SECTOR_MODULES_MAP[sectorKey], `Sector modules map missing for: ${sectorKey}`).toBeDefined();
      expect(SECTOR_PRIMARY_ROUTES[sectorKey], `Primary route missing for sector: ${sectorKey}`).toBeDefined();
      expect(SECTOR_PRIMARY_ROUTES[sectorKey]).toMatch(/^\/[a-z0-9_-]+(\/[a-z0-9_-]+)*$/);

      const modules = getSectorModules(sectorKey);
      expect(modules.length, `Modules list empty for sector: ${sectorKey}`).toBeGreaterThan(0);

      const defaults = getSectorDefaultFeatures(sectorKey);
      expect(defaults.length, `Default features empty for sector: ${sectorKey}`).toBeGreaterThan(0);
    }
  });
});
