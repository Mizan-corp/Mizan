import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";

// Mizan system app. "@/" is the shared kit (shared/frontend/src), "@app/" is this app.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  return {
    base: env.VITE_BASE || process.env.VITE_BASE || "/",
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@app": fileURLToPath(new URL("./src", import.meta.url)),
      "@activities": fileURLToPath(new URL("./src/activities", import.meta.url)),
        "@": fileURLToPath(new URL("../../shared/frontend/src", import.meta.url)),
      },
    },
    build: {
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
      port: 5173,
      strictPort: true,
      proxy: {
        "/api": {
          target: "http://localhost:8000",
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api/, ""),
        },
        // Dev only: the backend serves uploaded site assets (logos, covers)
        // at /uploads on the app origin; preview pages reference them by
        // relative URL exactly like production.
        "/uploads": {
          target: "http://localhost:8000",
          changeOrigin: true,
        },
      },
    },
  };
});
