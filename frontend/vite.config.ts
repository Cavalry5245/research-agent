import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const backend = "http://127.0.0.1:8888";

function apiProxy() {
  return {
    target: backend,
    bypass(req) {
      if (req.method === "GET" && req.headers.accept?.includes("text/html")) {
        return "/index.html";
      }
      return undefined;
    }
  };
}

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": apiProxy(),
      "/agent": apiProxy(),
      "/health": apiProxy(),
      "/kb": apiProxy(),
      "/library": apiProxy(),
      "/papers": apiProxy(),
      "/qa": apiProxy(),
      "/research-pipeline": apiProxy(),
      "/research-runs": apiProxy(),
      "/system": apiProxy(),
      "/tasks": apiProxy()
    }
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    globals: true
  }
});
