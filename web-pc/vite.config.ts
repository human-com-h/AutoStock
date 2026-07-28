import vue from "@vitejs/plugin-vue";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [vue()],
    server: {
      proxy: {
        "/api": {
          target: env.AUTOSTOCK_DEV_API_TARGET || "http://127.0.0.1:8756",
          changeOrigin: true,
        },
      },
    },
  };
});
