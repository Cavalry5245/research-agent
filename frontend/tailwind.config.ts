import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#f7f8fa",
        panel: "#ffffff",
        ink: "#172033",
        muted: "#667085",
        line: "#d9dee7",
        accent: "#2563eb"
      },
      boxShadow: {
        panel: "0 1px 2px rgba(16, 24, 40, 0.06)"
      }
    }
  },
  plugins: []
} satisfies Config;
