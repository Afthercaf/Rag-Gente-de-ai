// vite.config.js
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import mkcert from 'vite-plugin-mkcert'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  const apiUrl = env.VITE_API_URL?.trim()

  if (mode === 'production' && !apiUrl) {
    throw new Error('VITE_API_URL debe estar definida durante el build del frontend')
  }

  const connectSources = ["'self'"]
  if (apiUrl) {
    let apiOrigin
    try {
      apiOrigin = new URL(apiUrl).origin
    } catch {
      throw new Error('VITE_API_URL debe ser una URL absoluta válida')
    }
    connectSources.push(apiOrigin)
  }

  const csp = [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    `connect-src ${connectSources.join(' ')}`,
    "img-src 'self' data:",
    "font-src 'self'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join('; ')

  return {
    plugins: [
      react(),
      ...(mode === 'development' ? [mkcert()] : []),
      {
        name: 'runtime-csp',
        transformIndexHtml(html) {
          return html.replace('__APP_CSP__', csp)
        },
      },
    ],
  }
})
