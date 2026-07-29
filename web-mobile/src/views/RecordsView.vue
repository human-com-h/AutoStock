<script setup lang="ts">
import { computed, onActivated, onMounted, ref } from "vue";
import { showConfirmDialog, showSuccessToast } from "vant";
import { useRouter } from "vue-router";
import { recentOrders, voidPendingOrder, type OrderKind } from "../services/orders";
import { useAppStore } from "../stores/app";

type RecordRow = Awaited<ReturnType<typeof recentOrders>>[number];
type RecordFilter = "all" | OrderKind;
const router = useRouter();
const appStore = useAppStore();
const rows = ref<RecordRow[]>([]);
const keyword = ref("");
const activeFilter = ref<RecordFilter>("all");
const filteredRows = computed(() => {
  const needle = keyword.value.trim().toLowerCase();
  return rows.value
    .filter((row) => activeFilter.value === "all" || row.kind === activeFilter.value)
    .filter((row) =>
      [row.order.order_no, row.partName, row.partnerName]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(needle)),
    );
});
const grouped = computed(() => {
  const result = new Map<string, RecordRow[]>();
  for (const row of filteredRows.value) {
    const group = result.get(row.order.order_date) || [];
    group.push(row);
    result.set(row.order.order_date, group);
  }
  return Array.from(result.entries());
});

async function load(): Promise<void> {
  rows.value = await recentOrders();
}

async function voidOrder(kind: OrderKind, orderId: string): Promise<void> {
  await showConfirmDialog({
    title: "撤销这笔本地单据？",
    message: "仅会撤销尚未同步的当日记录，库存口径将立即恢复。",
  });
  await voidPendingOrder(kind, orderId);
  await Promise.all([load(), appStore.refreshPending()]);
  showSuccessToast("已撤销");
}

function openDetail(row: RecordRow): void {
  router.push(`/records/${row.kind}/${row.order.id}`);
}

function canVoid(row: RecordRow): boolean {
  return (
    row.order.sync_status === "pending" &&
    row.order.order_date === new Date().toLocaleDateString("sv-SE")
  );
}

onMounted(load);
onActivated(load);
</script>

<template>
  <section class="page records-page">
    <div class="queue-summary">
      <div>
        <strong>{{ appStore.pendingCount }}</strong>
        <span>笔待同步</span>
      </div>
      <p>待同步记录已安全保存在本机，回到电脑所在 WiFi 后再处理。</p>
    </div>
    <van-search
      v-model="keyword"
      shape="round"
      background="transparent"
      placeholder="搜索单号、配件或往来单位"
    />
    <div class="record-filters" role="group" aria-label="单据类型">
      <button
        v-for="option in [
          { value: 'all', label: '全部' },
          { value: 'purchase', label: '采购' },
          { value: 'sale', label: '销售' },
        ]"
        :key="option.value"
        type="button"
        :class="{ active: activeFilter === option.value }"
        @click="activeFilter = option.value as RecordFilter"
      >
        {{ option.label }}
      </button>
    </div>
    <template v-for="[date, records] in grouped" :key="date">
      <h2 class="date-title">{{ date }}</h2>
      <div class="surface record-list">
        <button
          v-for="row in records"
          :key="row.order.id"
          type="button"
          class="record-row"
          @click="openDetail(row)"
        >
          <div class="record-kind" :class="row.kind">
            <van-icon :name="row.kind === 'purchase' ? 'down' : 'upgrade'" />
          </div>
          <div class="record-main">
            <strong>{{ row.partName }}</strong>
            <span>{{ row.order.order_no }}</span>
            <small>
              {{ row.kind === "purchase" ? "采购入库" : "销售出库" }}
              · {{ row.itemCount }} 项
              <template v-if="row.partnerName"> · {{ row.partnerName }}</template>
            </small>
          </div>
          <div class="record-value">
            <strong>¥{{ (row.order.total_amount / 100).toFixed(2) }}</strong>
            <span :class="{ pending: row.order.sync_status === 'pending' }">
              {{ row.order.sync_status === "pending" ? "待同步" : "已入账" }}
            </span>
            <span
              v-if="canVoid(row)"
              class="void-action"
              role="button"
              tabindex="0"
              @click.stop="voidOrder(row.kind, row.order.id)"
              @keydown.enter.stop="voidOrder(row.kind, row.order.id)"
            >
              撤销
            </span>
          </div>
        </button>
      </div>
    </template>
    <div v-if="!filteredRows.length" class="surface empty-state">
      <strong>{{ rows.length ? "没有匹配的单据" : "近 90 天暂无记录" }}</strong>
      {{ rows.length ? "请调整关键词或单据类型。" : "入库或出库后会显示在这里。" }}
    </div>
  </section>
</template>

<style scoped>
.queue-summary {
  display: flex; align-items: center; gap: 14px; padding: 14px 16px; border-radius: 12px;
  color: white; background: linear-gradient(135deg, #08375d, #075186);
}
.queue-summary div { min-width: 72px; text-align: center; }
.queue-summary strong { display: block; font-size: 25px; }
.queue-summary span { font-size: 11px; opacity: .8; }
.queue-summary p { margin: 0; font-size: 12px; line-height: 1.6; opacity: .88; }
.records-page :deep(.van-search) { padding: 14px 0 8px; }
.records-page :deep(.van-search__content) { border: 1px solid #d0dae6; background: white; }
.record-filters { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; padding: 4px; border-radius: 10px; background: #e8edf4; }
.record-filters button { height: 34px; border: 0; border-radius: 7px; color: #63748a; background: transparent; font-size: 12px; }
.record-filters button.active { color: #1765d4; background: white; box-shadow: 0 2px 8px rgb(33 62 95 / 9%); font-weight: 700; }
.date-title { margin: 20px 2px 8px; color: #56677d; font-size: 13px; }
.record-list { overflow: hidden; }
.record-row { width: 100%; display: grid; grid-template-columns: 40px minmax(0, 1fr) auto; gap: 10px; padding: 14px; border: 0; border-bottom: 1px solid #edf1f5; color: #172b45; background: white; text-align: left; }
.record-row:last-child { border-bottom: 0; }
.record-kind { width: 38px; height: 38px; display: grid; place-items: center; border-radius: 10px; color: #198b4b; background: #eaf9f0; }
.record-kind.sale { color: #176ae8; background: #eaf3ff; }
.record-main strong, .record-main span, .record-main small { display: block; }
.record-main span { margin: 4px 0; color: #63748a; font-size: 11px; }
.record-main small { color: #8490a0; }
.record-value { text-align: right; }
.record-value strong, .record-value span { display: block; }
.record-value span { margin: 5px 0; color: #2f8951; font-size: 11px; }
.record-value span.pending { color: var(--orange); }
.void-action { padding: 4px 0; color: #e05048; font-size: 12px; }
</style>
