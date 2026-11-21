import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const api = process.env.QUERYA_API_URL ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: Object.fromEntries(
      ['/ask', '/runs', '/schema', '/health'].map((path) => [path, { target: api, changeOrigin: true }]),
    ),
  },
  build: {
    chunkSizeWarningLimit: 900,
  },
})
