import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

const servidor = process.env.API_URL ?? 'http://localhost:3333';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      output: { manualChunks: { graficos: ['recharts'], base: ['react', 'react-dom', 'react-router-dom'] } },
    },
  },
  server: {
    port: 5173,
    proxy: Object.fromEntries(['/api', '/webhooks', '/publico', '/descadastro'].map((p) => [p, servidor])),
  },
});
