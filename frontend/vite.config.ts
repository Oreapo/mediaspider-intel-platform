import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'

const frontendRoot = fileURLToPath(new URL('.', import.meta.url))
const projectRoot = fileURLToPath(new URL('..', import.meta.url))

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, projectRoot, '')
  const apiTarget =
    process.env.MEDIASPIDER_API_TARGET ||
    env.MEDIASPIDER_API_TARGET ||
    'http://127.0.0.1:8180'
  const apiProxy = {
    '/api': {
      target: apiTarget,
      changeOrigin: true,
    },
    '/health': {
      target: apiTarget,
      changeOrigin: true,
    },
  }

  return {
    root: frontendRoot,
    envDir: projectRoot,
    plugins: [vue()],
    server: {
      host: '127.0.0.1',
      port: 5173,
      fs: {
        allow: [frontendRoot],
      },
      proxy: apiProxy,
    },
    preview: {
      host: '127.0.0.1',
      port: 4173,
      proxy: apiProxy,
    },
  }
})
