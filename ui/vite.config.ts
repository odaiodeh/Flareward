import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import themePlugin from "@replit/vite-plugin-shadcn-theme-json";
import path from "path";
import runtimeErrorOverlay from "@replit/vite-plugin-runtime-error-modal";
import { visualizer } from 'rollup-plugin-visualizer'; // Import the build analyzer plugin

const parsedDevPort = parseInt(process.env.DEV_PORT ?? '', 10);

export default defineConfig({
  plugins: [
    react(),
    runtimeErrorOverlay(),
    themePlugin(),
    ...(process.env.NODE_ENV !== "production" &&
    process.env.REPL_ID !== undefined
      ? [
          await import("@replit/vite-plugin-cartographer").then((m) =>
            m.cartographer(),
          ),
        ]
      : []),
      process.env.NODE_ENV !== "production" && visualizer({
        open: true, // Automatically opens the report in your browser after build
        filename: 'bundle-report.html', // Name of the generated report file
        gzipSize: true, // Show sizes after gzip compression
        brotliSize: true, // Show sizes after brotli compression (if available)
    }),
  ],
  server: {
    port: Number.isFinite(parsedDevPort) ? parsedDevPort : 5173,
    host: process.env.DEV_HOST || undefined,
    proxy: {
      '/api': {
        target: process.env.PLATFORM_HOST,
        changeOrigin: true,
      },
      '/identity/api': {
        target: process.env.IDENTITY_HOST,
        changeOrigin: true,
        rewrite: (pathname) => pathname.replace(/^\/identity\/api/, '/api'),
      },
    }
  },

  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "client", "src"),
      "@shared": path.resolve(import.meta.dirname, "shared"),
      "@assets": path.resolve(import.meta.dirname, "attached_assets"),
    },
  },
  root: path.resolve(import.meta.dirname, "client"),
  build: {
    outDir: path.resolve(import.meta.dirname, "build"),
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules') && id.includes('react')) {
            return 'react-vendor'; // Separate React/ReactDOM
          }
          if (id.includes('node_modules')) {
            return 'vendor'; // Other node_modules
          }
        },
      },
    },
  },
});