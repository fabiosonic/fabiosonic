import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// O build vai direto para o pacote Python (servido pelo FastAPI em http://127.0.0.1:8765)
export default defineConfig({
  plugins: [react()],
  build: { outDir: "../backend/moxml/web", emptyOutDir: true },
  server: { proxy: { "/api": "http://127.0.0.1:8765" } },
});
