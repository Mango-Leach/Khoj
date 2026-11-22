import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import basicSsl from "@vitejs/plugin-basic-ssl";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";

// Mic, camera and service workers need a secure context. On the laptop, http://localhost is one, so
// `npm run dev` is plain http with no certificate warning. A phone on the Wi-Fi needs real HTTPS:
// `npm run dev:lan` serves it with a self-signed certificate (accept the warning once on the phone).
const API_TARGET = process.env.KHOJ_API ?? "http://localhost:8000";

export default defineConfig(({ mode }) => {
  const lan = mode === "lan";
  return {
    plugins: [
      react(),
      tailwindcss(),
      ...(lan ? [basicSsl()] : []),
      VitePWA({
        registerType: "autoUpdate",
        manifest: {
          name: "KHOJ",
          short_name: "KHOJ",
          description: "Speak your skill. Find your first income.",
          theme_color: "#2433a6",
          background_color: "#f4f5f9",
          display: "standalone",
          start_url: "/",
          icons: [
            { src: "icon-192.png", sizes: "192x192", type: "image/png" },
            { src: "icon-512.png", sizes: "512x512", type: "image/png" },
            {
              src: "icon-512-maskable.png",
              sizes: "512x512",
              type: "image/png",
              purpose: "maskable",
            },
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
      host: lan,
      port: 5173,
      // One HTTPS origin for the phone: the page and the API share it, so no mixed content.
      proxy: { "/api": { target: API_TARGET, changeOrigin: true, xfwd: true } },
    },
    preview: {
      host: true,
      proxy: { "/api": { target: API_TARGET, changeOrigin: true, xfwd: true } },
    },
    test: { environment: "node" },
  };
});
