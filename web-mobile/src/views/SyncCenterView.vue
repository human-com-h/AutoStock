<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { showFailToast, showSuccessToast } from "vant";
import type { SyncHistoryRow } from "../db/schema";
import { recentSyncHistory } from "../services/sync";
import { useAppStore } from "../stores/app";

const appStore = useAppStore();
const history = ref<SyncHistoryRow[]>([]);
const syncing = computed(() => appStore.connection === "syncing");

async function load(): Promise<void> {
  await appStore.refreshPending();
  history.value = await recentSyncHistory();
}

async function syncNow(): Promise<void> {
  try {
    await appStore.syncNow();
    showSuccessToast("同步完成");
  } catch (error) {
    showFailToast(error instanceof Error ? error.message : "同步失败");
  } finally {
    await load();
  }
}

function formatTime(value: string | null): string {
  return value?.replace("T", " ").slice(0, 16) || "暂无";
}

onMounted(load);
</script>

<template>
  <section class="page sync-page">
    <div class="sync-hero surface">
      <div class="sync-count">
        <small>本机待同步</small>
        <strong>{{ appStore.pendingCount }}</strong>
        <span>笔单据</span>
      </div>
      <p>手机先保存本地数据；回到与电脑相同的局域网后，先上传流水、再拉取 PC 增量。</p>
      <van-button
        type="primary"
        block
        class="primary-action"
        :loading="syncing"
        :disabled="appStore.connection === 'offline'"
        @click="syncNow"
      >
        {{ appStore.connection === "offline" ? "电脑当前不可达" : "立即同步" }}
      </van-button>
      <div class="last-sync">
        <span>上次成功同步</span><strong>{{ formatTime(appStore.lastSyncAt) }}</strong>
      </div>
      <p v-if="appStore.lastSyncError" class="error-copy">{{ appStore.lastSyncError }}</p>
    </div>

    <h2 class="section-title">同步记录</h2>
    <div class="surface history-list">
      <div v-for="row in history" :key="row.id" class="history-row">
        <span class="result-dot" :class="row.result" />
        <div>
          <strong>{{ row.message }}</strong>
          <small>{{ formatTime(row.started_at) }}</small>
        </div>
        <span class="counts">↑{{ row.pushed_count }} ↓{{ row.pulled_count }}</span>
      </div>
      <div v-if="!history.length" class="empty-state">暂无同步记录</div>
    </div>
  </section>
</template>

<style scoped>
.sync-hero { padding: 20px; }
.sync-count { display: flex; align-items: baseline; gap: 7px; }
.sync-count small { color: var(--muted); }
.sync-count strong { color: var(--blue); font-size: 44px; line-height: 1; }
.sync-count span { color: var(--muted); }
.sync-hero > p { color: var(--muted); font-size: 12px; line-height: 1.7; }
.last-sync { display: flex; justify-content: space-between; margin-top: 16px; color: var(--muted); font-size: 12px; }
.last-sync strong { color: #30445f; }
.error-copy { color: #d94747 !important; }
.history-list { overflow: hidden; }
.history-row { display: grid; grid-template-columns: 10px 1fr auto; gap: 11px; align-items: center; padding: 14px; border-bottom: 1px solid #edf1f5; }
.history-row:last-child { border-bottom: 0; }
.history-row strong, .history-row small { display: block; }
.history-row strong { font-size: 13px; }
.history-row small, .counts { margin-top: 5px; color: var(--muted); font-size: 11px; }
.result-dot { width: 8px; height: 8px; border-radius: 50%; background: #36b66a; }
.result-dot.partial { background: #e99a25; }
.result-dot.failed { background: #d94747; }
</style>
