import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The dev server proxies /api to the FastAPI backend so the browser only ever
// talks to one origin (no CORS needed in development).
//
// Default target is http://localhost:8000 (the contract). API_PROXY_TARGET overrides it
// when port 8000 is already in use on the host machine.
// Example: API_PROXY_TARGET=http://localhost:8001 npm run dev
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const target = env.API_PROXY_TARGET || "http://localhost:8000";
  return {
    plugins: [react(), tailwindcss()],
    build: {
      // Recharts is most of the bundle; keep it in its own cacheable chunk.
      rollupOptions: { output: { manualChunks: { recharts: ["recharts"] } } },
    },
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        "/api": { target, changeOrigin: true },
      },
    },
  };
});
