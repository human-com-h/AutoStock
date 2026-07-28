<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import { useRouter } from "vue-router";
import { useAppStore } from "../stores/app";

const route = useRoute();
const router = useRouter();
const appStore = useAppStore();
const title = computed(() => String(route.meta.title || "AutoStock"));
</script>

<template>
  <header class="app-header">
    <h1>{{ title }}</h1>
    <button
      class="connection-state"
      :class="[appStore.connection, { recommended: appStore.syncRecommended }]"
      type="button"
      @click="router.push('/sync')"
    >
      <span class="status-dot" />
      <span>{{ appStore.statusText }}</span>
    </button>
  </header>
</template>

<style scoped>
.connection-state { border: 0; color: inherit; background: transparent; text-align: right; }
.connection-state.recommended { color: #ffd58a; }
</style>
