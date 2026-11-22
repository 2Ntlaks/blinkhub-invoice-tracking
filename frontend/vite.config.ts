import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The dev server proxies /api to the FastAPI backend so the browser only ever
// talks to one origin (no CORS needed in development).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    // Recharts is most of the bundle; keep it in its own cacheable chunk.
    rollupOptions: { output: { manualChunks: { recharts: ["recharts"] } } },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
