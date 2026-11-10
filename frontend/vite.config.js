import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import fs from "node:fs";
import path from "node:path";

const voiceWeb = fileURLToPath(new URL("../voice-core/web", import.meta.url));
const demoData = fileURLToPath(new URL("./demo", import.meta.url));

// `vite build --mode demo` (npm run build:demo): the static Vercel demo. frontend/demo/ (recorded snapshots and
// audio, refreshed by scripts/snapshot_demo.py) is served at /demo/ and copied into dist/demo. The normal build
// never sees it.
const TYPES = { ".json": "application/json", ".xml": "application/xml", ".wav": "audio/wav", ".mp3": "audio/mpeg" };
function demoFiles() {
  return {
    name: "pukaar-demo-files",
    configureServer(server) {
      server.middlewares.use("/demo", (req, res, next) => {
        const file = path.join(demoData, decodeURIComponent(req.url.split("?")[0]));
        if (!file.startsWith(demoData) || !fs.existsSync(file) || !fs.statSync(file).isFile()) return next();
        res.setHeader("Content-Type", TYPES[path.extname(file)] || "application/octet-stream");
        fs.createReadStream(file).pipe(res);
      });
    },
    writeBundle(options) {
      fs.cpSync(demoData, path.join(options.dir, "demo"), { recursive: true });
    },
  };
}

export default defineConfig(({ mode }) => ({
  plugins: [react(), mode === "demo" && demoFiles()],
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
}));
