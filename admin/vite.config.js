import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/admin/',
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/admin/api': 'http://localhost:8000',
    }
  },
  build: {
    outDir: '../portal/static/admin',
    emptyOutDir: true,
  }
})
