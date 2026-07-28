import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  base: "/m/",
  plugins: [
    vue(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["pwa-192.png", "pwa-512.png"],
      manifest: {
        name: "AutoStock 库存助手",
        short_name: "AutoStock",
        description: "汽车零部件离线进销存助手",
        theme_color: "#062d50",
        background_color: "#f4f7fb",
        display: "standalone",
        start_url: "/m/",
        scope: "/m/",
        icons: [
          { src: "/m/pwa-192.png", sizes: "192x192", type: "image/png" },
          { src: "/m/pwa-512.png", sizes: "512x512", type: "image/png" },
        ],
      },
      workbox: {
        navigateFallback: "/m/index.html",
        navigateFallbackDenylist: [/^\/api\//],
        runtimeCaching: [
          {
            urlPattern: /^https?:\/\/[^/]+\/api\//,
            handler: "NetworkOnly",
          },
        ],
      },
    }),
  ],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8756",
        changeOrigin: true,
      },
    },
  },
});
