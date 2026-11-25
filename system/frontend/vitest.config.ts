import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

export default defineConfig({
  test: { environment: "node", include: ["src/**/*.test.ts", "src/**/*.test.tsx"] },
  resolve: {
    alias: {
      "@app": fileURLToPath(new URL("./src", import.meta.url)),
      "@activities": fileURLToPath(new URL("./src/activities", import.meta.url)),
      "@": fileURLToPath(new URL("../../shared/frontend/src", import.meta.url)),
    },
  },
});
