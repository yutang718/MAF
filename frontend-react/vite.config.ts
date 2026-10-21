import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // Security governance service (compliance/); listed first so it wins over the MAF catch-all.
      '/api/v1/governance': {
        target: process.env.GOVERN_DEV_URL || 'http://localhost:8100',
        changeOrigin: true,
      },
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
