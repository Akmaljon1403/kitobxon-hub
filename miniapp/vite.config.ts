import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The Mini App is served by the backend under /app/ in production.
// During development `npm run dev` proxies API calls to a locally running backend.
export default defineConfig({
  base: '/app/',
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
  build: {
    target: 'es2020',
    sourcemap: false,
  },
})
