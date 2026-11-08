import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

const voiceWeb = fileURLToPath(new URL("../voice-core/web", import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@voice": voiceWeb } },
  server: {
    port: 5192,
    fs: { allow: [".", voiceWeb] },
    proxy: {
      "/api": "http://127.0.0.1:8766",
      "/ws": { target: "ws://127.0.0.1:8766", ws: true },
    },
  },
  build: { target: "es2022" },
});
