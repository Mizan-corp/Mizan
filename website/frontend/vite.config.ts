import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";

// Mizan website app. "@/" is the shared kit (system/core/frontend/src), "@app/" is this app.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  return {
    base: env.VITE_BASE || process.env.VITE_BASE || "/",
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@app": fileURLToPath(new URL("./src", import.meta.url)),
        "@": fileURLToPath(new URL("../../system/core/frontend/src", import.meta.url)),
      },
    },
    build: {
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
