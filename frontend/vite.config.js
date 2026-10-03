import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const api = 'http://localhost:8000'

// In dev, forward API calls to the FastAPI backend; in production FastAPI serves dist/ itself.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/chat': api, '/usage': api, '/attacks': api, '/replay': api, '/health': api,
    },
  },
})
