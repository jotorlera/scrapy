import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Frontend de TORNILLO SUELTO (motor ATLAS). En desarrollo, /api se redirige a la API FastAPI local.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: false,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
    chunkSizeWarningLimit: 1200,
  },
})
