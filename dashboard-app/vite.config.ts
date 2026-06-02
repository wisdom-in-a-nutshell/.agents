import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// Served by the Python control-plane server under the /dashboard/ path.
// In dev, proxy the API + source routes to that same local server (:8765).
const API_TARGET = process.env.CONTROL_PLANE_ORIGIN ?? 'http://127.0.0.1:8765';

export default defineConfig({
  base: '/dashboard/',
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5180,
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: true },
      '/source': { target: API_TARGET, changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
