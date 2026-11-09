import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Mizan Setup's wizard (served to the Tauri window; works offline).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  clearScreen: false,
  server: { port: 5180, strictPort: true },
  build: { target: "es2022", chunkSizeWarningLimit: 1200 },
});
