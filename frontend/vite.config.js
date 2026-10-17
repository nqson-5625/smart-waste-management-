import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'Smart Waste', short_name: 'SmartWaste', lang: 'vi',
        theme_color: '#1976d2', background_color: '#ffffff', display: 'standalone',
        icons: [{ src: 'icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' }],
      },
    }),
  ],
  // Gọi /api/v1/... trên cùng origin, Vite chuyển tiếp sang backend => không dính CORS khi dev
  server: { proxy: { '/api': 'http://localhost:8000' } },
})
