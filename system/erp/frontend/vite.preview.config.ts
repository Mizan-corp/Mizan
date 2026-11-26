import base from "./vite.config";
import { defineConfig } from "vite";
import { fileURLToPath, URL } from "node:url";
export default defineConfig(async (env) => {
  const b = typeof base === "function" ? await base(env) : base;
  return {
    ...b,
    build: {
      ...b.build,
      rollupOptions: {
        ...b.build?.rollupOptions,
        input: {
          studio: fileURLToPath(new URL("./studio.html", import.meta.url)),
          "studio-preview": fileURLToPath(new URL("./studio-preview.html", import.meta.url)),
        },
      },
    },
  };
});
