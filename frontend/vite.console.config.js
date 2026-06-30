import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  base: "/devconsole/",
  build: {
    outDir: "../static/console",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        index: resolve(__dirname, "console.html"),
      },
    },
  },
  server: {
    port: 5174,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
