import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Local `npm run dev` only: forward /api to the backend so the app can
    // use relative URLs, same as in production behind the ALB.
    proxy: { "/api": process.env.API_PROXY_TARGET || "http://localhost:8000" },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/setupTests.js",
    globals: true,
  },
});
