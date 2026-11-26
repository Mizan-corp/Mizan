import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

export default defineConfig({
  // tsconfig uses react-jsx; system/core/frontend has no tsconfig of its own, so without
  // this the classic transform leaves 'React is not defined' in shared components.
  esbuild: { jsx: "automatic" },
  test: { environment: "node", include: ["src/**/*.test.ts", "src/**/*.test.tsx"] },
  resolve: {
    alias: {
      "@app": fileURLToPath(new URL("./src", import.meta.url)),
      "@activities": fileURLToPath(new URL("./src/activities", import.meta.url)),
      "@": fileURLToPath(new URL("../../core/frontend/src", import.meta.url)),
    },
  },
});
