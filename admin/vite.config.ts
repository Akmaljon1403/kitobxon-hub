import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The Admin Panel is served by the backend under /admin/ in production.
// During development `npm run dev` proxies API calls to a locally running backend.
export default defineConfig({
  base: '/admin/',
  plugins: [react(), tailwindcss()],
  server: {
    port: 5174,
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
