import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  // The backend serves its routes at the root (e.g. /subjects), so the
  // frontend calls them under /api and the dev server strips the prefix.
  // Going through the proxy means the browser only ever talks to the Vite
  // origin, so no CORS configuration is needed during development.
  const backendTarget = env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': {
          target: backendTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
          // Generating a course or a lesson with a local LLM can be slow.
          timeout: 300000,
          proxyTimeout: 300000,
        },
      },
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: './src/test/setup.js',
      css: false,
    },
  }
})
