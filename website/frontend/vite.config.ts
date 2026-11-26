import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";

// Mizan website app. "@/" is the shared kit (system/core/frontend/src), "@app/" is this app.
// `npm run build` makes the browser bundle, then the build-time renderer (--ssr), then
// scripts/prerender.mjs writes every public page as HTML (ADR-016).
export default defineConfig(({ mode, isSsrBuild }) => {
  const env = loadEnv(mode, process.cwd(), "");

  return {
    base: env.VITE_BASE || process.env.VITE_BASE || "/",
    plugins: [react(), tailwindcss()],
    define: { __BUILD_YEAR__: JSON.stringify(new Date().getFullYear()) },
    resolve: {
      alias: {
        "@app": fileURLToPath(new URL("./src", import.meta.url)),
        "@": fileURLToPath(new URL("../../system/core/frontend/src", import.meta.url)),
      },
    },
    build: isSsrBuild
      ? { outDir: "dist-ssr", emptyOutDir: true, copyPublicDir: false }
      : {
          // The prerender reads it to preload each page's own chunk.
          manifest: true,
          rollupOptions: {
            output: {
              manualChunks: {
                vendor: ["react", "react-dom", "react-router-dom"],
                motion: ["motion", "framer-motion", "motion-dom"],
                query: ["@tanstack/react-query"],
                icons: ["lucide-react"],
              },
            },
          },
        },
    // The renderer runs once at build time: bundle everything, Node needs nothing installed.
    ssr: { noExternal: true },
    server: {
      fs: { allow: ["../.."] },
      port: 5174,
      strictPort: true,
      proxy: {
        "/api": {
          target: "http://localhost:8001",
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api/, ""),
        },
      },
    },
  };
});
