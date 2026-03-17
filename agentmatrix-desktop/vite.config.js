import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    strictPort: true, // Tauri requires a fixed port
    proxy: {
      // 🔑 关键：代理后端 API
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // 🔑 关键：代理 WebSocket
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
  // Tauri expects a fixed directory structure
  build: {
    target: process.env.TAURI_PLATFORM == 'windows' ? 'chrome105' : 'safari13',
    // Don't minify for debug builds
    minify: !process.env.TAURI_DEBUG ? 'esbuild' : false,
    // Produce sourcemaps for debug builds
    sourcemap: !!process.env.TAURI_DEBUG,
  },
})
