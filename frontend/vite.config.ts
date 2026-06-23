import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const backend = env.VITE_API_BASE_URL || "http://127.0.0.1:8888";

  function apiProxy() {
    return {
      target: backend,
      bypass(req: any) {
        if (req.method === "GET" && req.headers.accept?.includes("text/html")) {
          return "/index.html";
        }
        return undefined;
      }
    };
  }

  return {
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
  };
});
