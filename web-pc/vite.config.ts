import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      "/api": {
        target: "https://127.0.0.1:8756",
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
