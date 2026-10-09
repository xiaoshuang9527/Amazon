import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  },
  server: {
    // 固定端口，避免与其它项目的 Vite（默认 5173/5174）抢占后地址漂移。
    // strictPort=true 表示端口被占时直接报错退出，而不是静默换端口。
    port: 5180,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
