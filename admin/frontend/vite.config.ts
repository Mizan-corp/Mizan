import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";

// Mizan admin app. "@/" is the shared kit (shared/frontend/src), "@app/" is this app.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  // Served under a path on the one domain (ADR-008, e.g. /owner/): the files go in a folder of
  // that name, so the same build works on the project's own address and behind the main domain.
  const base = env.VITE_BASE || process.env.VITE_BASE || "/";
  const folder = base.replace(/^\/+|\/+$/g, "");

  return {
    base,
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@app": fileURLToPath(new URL("./src", import.meta.url)),
        "@": fileURLToPath(new URL("../../shared/frontend/src", import.meta.url)),
      },
    },
    build: {
      outDir: folder ? `dist/${folder}` : "dist",
      emptyOutDir: true,
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: ["react", "react-dom", "react-router-dom"],
            motion: ["motion", "framer-motion", "motion-dom"],
            query: ["@tanstack/react-query"],
          charts: ["recharts"],
            icons: ["lucide-react"],
          },
        },
      },
    },
    server: {
      fs: { allow: ["../.."] },
      port: 5175,
      strictPort: true,
      proxy: {
        "/api": {
          target: "http://localhost:8002",
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api/, ""),
        },
      },
    },
  };
});
