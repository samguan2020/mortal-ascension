import { defineConfig } from "vite";

const localApi = "http://127.0.0.1:8000";

export default defineConfig({
  server: {
    host: "127.0.0.1",
    port: 5174,
    strictPort: true,
    proxy: {
      "/api": { target: localApi },
      "/healthz": { target: localApi },
    },
  },
});
