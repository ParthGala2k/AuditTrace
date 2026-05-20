import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/audit':    'http://localhost:8000',
      '/evaluate': 'http://localhost:8000',
      '/fix':      'http://localhost:8000',
      '/policies': 'http://localhost:8000',
      '/history':  'http://localhost:8000',
      '/eval':     'http://localhost:8000',
      '/health':   'http://localhost:8000',
    },
  },
})
