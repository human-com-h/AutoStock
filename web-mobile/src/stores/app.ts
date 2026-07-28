import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { getMeta } from "../db/schema";
import { probeHealth } from "../services/api";
import { pendingCount as loadPendingCount } from "../services/orders";
import { synchronize } from "../services/sync";

export type ConnectionState = "connected" | "offline" | "syncing";

export const useAppStore = defineStore("app", () => {
  const connection = ref<ConnectionState>("offline");
  const pendingCount = ref(0);
  const initialized = ref(false);
  const lastSyncAt = ref<string | null>(null);
  const lastSyncError = ref<string | null>(null);
  const syncRecommended = ref(false);
  let timer: number | null = null;
  let syncTimer: number | null = null;

  const statusText = computed(() => {
    if (connection.value === "syncing") return "正在同步";
    if (connection.value === "connected") {
      return pendingCount.value
        ? `已连接 PC · 待同步 ${pendingCount.value} 笔`
        : "已连接 PC";
    }
    return pendingCount.value
      ? `离线记账中 · 待同步 ${pendingCount.value} 笔`
      : "离线记账中";
  });

  async function refreshPending(): Promise<void> {
    pendingCount.value = await loadPendingCount();
  }

  async function refreshConnection(): Promise<void> {
    if (connection.value === "syncing") return;
    const wasOffline = connection.value === "offline";
    connection.value = (await probeHealth()) ? "connected" : "offline";
    if (wasOffline && connection.value === "connected" && pendingCount.value > 0) {
      syncRecommended.value = true;
    }
  }

  async function syncNow(silent = false): Promise<void> {
    if (connection.value === "syncing") return;
    connection.value = "syncing";
    lastSyncError.value = null;
    try {
      await synchronize();
      lastSyncAt.value = await getMeta("last_sync_at");
      syncRecommended.value = false;
      await refreshPending();
      connection.value = "connected";
    } catch (error) {
      lastSyncError.value = error instanceof Error ? error.message : "同步失败";
      connection.value = "offline";
      if (!silent) throw error;
    }
  }

  async function bootstrapState(): Promise<void> {
    initialized.value = Boolean(await getMeta("initialized_at"));
    lastSyncAt.value = await getMeta("last_sync_at");
    await Promise.all([refreshPending(), refreshConnection()]);
    if (initialized.value && connection.value === "connected") {
      await syncNow(true);
    }
    if (timer === null) {
      timer = window.setInterval(refreshConnection, 30_000);
      window.addEventListener("online", async () => {
        await refreshConnection();
        if (connection.value === "connected" && pendingCount.value > 0) {
          syncRecommended.value = true;
        }
      });
      window.addEventListener("offline", refreshConnection);
    }
    if (syncTimer === null) {
      syncTimer = window.setInterval(() => {
        if (initialized.value && connection.value === "connected") void syncNow(true);
      }, 10 * 60_000);
    }
  }

  function setSyncing(value: boolean): void {
    connection.value = value ? "syncing" : navigator.onLine ? "connected" : "offline";
  }

  return {
    connection,
    pendingCount,
    initialized,
    lastSyncAt,
    lastSyncError,
    syncRecommended,
    statusText,
    refreshPending,
    refreshConnection,
    bootstrapState,
    syncNow,
    setSyncing,
  };
});
