import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8888",
      "/agent": "http://127.0.0.1:8888",
      "/health": "http://127.0.0.1:8888",
      "/kb": "http://127.0.0.1:8888",
      "/library": "http://127.0.0.1:8888",
      "/papers": "http://127.0.0.1:8888",
      "/qa": "http://127.0.0.1:8888",
      "/research-runs": "http://127.0.0.1:8888",
      "/system": "http://127.0.0.1:8888",
      "/tasks": "http://127.0.0.1:8888"
    }
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    globals: true
  }
});
