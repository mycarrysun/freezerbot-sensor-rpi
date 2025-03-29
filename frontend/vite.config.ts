import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    // Generate self-contained static files
    assetsInlineLimit: 0,
    // Output to the Flask static folder
    outDir: '../raspberry_pi/static',
    // Ensures asset paths are relative
    assetsDir: '',
    rollupOptions: {
      output: {
        // Ensure main.js file has a consistent name
        entryFileNames: 'main.js',
        // Ensure asset files have consistent names
        assetFileNames: '[name][extname]'
      }
    }
  }
});
