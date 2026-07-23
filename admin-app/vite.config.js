import { fileURLToPath, URL } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  base: "/admin/",
  plugins: [react()],
  build: {
    outDir: fileURLToPath(new URL("../site/admin", import.meta.url)),
    emptyOutDir: true,
    manifest: true
  }
});
