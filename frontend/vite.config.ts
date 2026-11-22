import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import basicSsl from "@vitejs/plugin-basic-ssl";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";

// Mic, camera and service workers need a secure context. basic-ssl gives phones an
// HTTPS dev origin on the LAN (accept the certificate warning once). Swap in mkcert
// before the demo so the phone trusts the certificate.
const API_TARGET = process.env.KHOJ_API ?? "http://localhost:8000";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    basicSsl(),
    VitePWA({
      registerType: "autoUpdate",
      manifest: {
        name: "KHOJ",
        short_name: "KHOJ",
        description: "Speak your skill. Find your first income.",
        theme_color: "#1d4ed8",
        background_color: "#f7f9fd",
        display: "standalone",
        start_url: "/",
        icons: [
          { src: "icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "icon-512-maskable.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,svg}"], // the logo is an SVG, so it works offline too
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api\//],
        cleanupOutdatedCaches: true,
      },
      devOptions: { enabled: false }, // avoid stale service-worker builds while developing
    }),
  ],
  server: {
    host: true,
    port: 5173,
    // One HTTPS origin for the phone: the page and the API share it, so no mixed content.
    proxy: { "/api": { target: API_TARGET, changeOrigin: true, xfwd: true } },
  },
  preview: {
    host: true,
    proxy: { "/api": { target: API_TARGET, changeOrigin: true, xfwd: true } },
  },
  test: { environment: "node" },
});
