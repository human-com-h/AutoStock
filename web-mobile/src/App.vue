<script setup lang="ts">
import { computed, onMounted } from "vue";
import { useRoute } from "vue-router";
import AppHeader from "./components/AppHeader.vue";
import BottomNav from "./components/BottomNav.vue";
import { useAppStore } from "./stores/app";

const route = useRoute();
const appStore = useAppStore();
const chromeVisible = computed(() => route.meta.chrome !== false);
onMounted(appStore.bootstrapState);
</script>

<template>
  <div class="mobile-app">
    <AppHeader v-if="chromeVisible" />
    <main :class="{ 'with-chrome': chromeVisible }">
      <router-view />
    </main>
    <BottomNav v-if="chromeVisible" />
  </div>
</template>

<style>
:root {
  font-family: Inter, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
  color: #10223b;
  background: #f4f7fb;
  font-synthesis: none;
  --navy: #062d50;
  --blue: #1677ff;
  --orange: #ff6b00;
  --border: #dbe3ee;
  --muted: #6f7c90;
}
* { box-sizing: border-box; }
html, body, #app { margin: 0; min-height: 100%; background: #f4f7fb; }
body { min-width: 320px; }
button, input { font: inherit; }
.mobile-app { min-height: 100vh; }
main.with-chrome { padding: 72px 0 68px; }
.app-header {
  position: fixed;
  z-index: 20;
  inset: 0 0 auto;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: max(8px, env(safe-area-inset-top)) 18px 8px;
  color: white;
  background: linear-gradient(115deg, #052947, #063962);
  box-shadow: 0 2px 12px rgb(4 30 55 / 18%);
}
.app-header h1 { margin: 0; font-size: 21px; letter-spacing: .01em; }
.connection-state {
  display: flex;
  align-items: center;
  gap: 6px;
  max-width: 58%;
  font-size: 12px;
  white-space: nowrap;
}
.status-dot { width: 9px; height: 9px; border-radius: 50%; background: #9aa6b5; }
.connected .status-dot { background: #45d04f; box-shadow: 0 0 0 3px rgb(69 208 79 / 15%); }
.syncing .status-dot { background: #4fa4ff; animation: pulse 1s infinite; }
@keyframes pulse { 50% { opacity: .35; } }
.page { padding: 12px 14px 28px; }
.surface {
  background: white;
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: 0 7px 26px rgb(28 57 89 / 5%);
}
.section-title { margin: 22px 2px 10px; font-size: 16px; }
.empty-state { padding: 48px 22px; text-align: center; color: var(--muted); }
.empty-state strong { display: block; margin-bottom: 8px; color: #263951; }
.bottom-nav { padding-bottom: env(safe-area-inset-bottom); box-shadow: 0 -4px 20px rgb(20 47 77 / 8%); }
.money, .quantity { font-variant-numeric: tabular-nums; }
.quantity { color: var(--blue); font-weight: 750; }
.quantity.low { color: var(--orange); }
.primary-action {
  height: 48px !important;
  border: 0 !important;
  border-radius: 10px !important;
  font-weight: 700 !important;
  background: linear-gradient(135deg, #176cff, #1688ff) !important;
  box-shadow: 0 8px 18px rgb(22 119 255 / 20%);
}
</style>
