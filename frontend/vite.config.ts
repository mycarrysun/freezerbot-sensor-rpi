import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import { fileURLToPath, URL } from 'url'

// Flask backend paths
const FLASK_STATIC_DIR = '../raspberry_pi/static'
const FLASK_TEMPLATE_DIR = '../raspberry_pi/templates'

export default defineConfig({
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true
      }
    }
  },
  build: {
    // The main output directory
    outDir: FLASK_STATIC_DIR,

    // Ensure asset paths are relative
    assetsDir: '',

    // Generate separate index.html
    emptyOutDir: true,

    rollupOptions: {
      output: {
        // Ensure main.js file has consistent name
        entryFileNames: 'main.js',

        // Ensure CSS has consistent name
        assetFileNames: (assetInfo) => {
          const info = assetInfo.name.split('.')
          const extType = info[info.length - 1]

          if (/\.(css)$/i.test(assetInfo.name)) {
            return 'style.[ext]'
          }

          return '[name][extname]'
        },

        // Generate the index.html in the Flask templates directory
        // This allows Flask to serve it directly
        dir: FLASK_STATIC_DIR
      },

      // Handle index.html specially to put it in the templates folder
      input: {
        main: 'index.html',
      }
    }
  },

  // Special handling for the index.html
  // This moves the generated index.html from static to templates
  plugins: [
    vue(),
    {
      name: 'move-index-html',
      closeBundle: async () => {
        const fs = await import('fs/promises')
        try {
          // Move the generated index.html from static to templates
          await fs.copyFile(
            path.resolve(__dirname, `${FLASK_STATIC_DIR}/index.html`),
            path.resolve(__dirname, `${FLASK_TEMPLATE_DIR}/index.html`)
          )
          // Remove the original copy
          await fs.unlink(path.resolve(__dirname, `${FLASK_STATIC_DIR}/index.html`))
        } catch (e) {
          console.error('Failed to move index.html:', e)
        }
      }
    }
  ]
})