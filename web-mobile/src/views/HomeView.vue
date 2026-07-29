<script setup lang="ts">
import { computed, onActivated, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { getMeta } from "../db/schema";
import { getMobileBusinessOverview, type MobileBusinessOverview } from "../services/dashboard";
import { searchLocalParts, type PartWithStock } from "../services/inventory";
import { formatMoney } from "../utils/print";

const router = useRouter();
const keyword = ref("");
const rows = ref<PartWithStock[]>([]);
const loading = ref(false);
const initialized = ref(true);
const lowStockOnly = ref(false);
const overview = ref<MobileBusinessOverview>({
  salesAmount: 0,
  purchaseAmount: 0,
  orderCount: 0,
});
const visibleRows = computed(() => rows.value.slice(0, 200));
const lowCount = computed(
  () => rows.value.filter((row) => row.displayQuantity < Number(row.part.min_stock)).length,
);

async function load(): Promise<void> {
  loading.value = true;
  initialized.value = Boolean(await getMeta("initialized_at"));
  [rows.value, overview.value] = await Promise.all([
    searchLocalParts(keyword.value, lowStockOnly.value),
    getMobileBusinessOverview(),
  ]);
  loading.value = false;
}

function showLowStock(): void {
  lowStockOnly.value = !lowStockOnly.value;
  load();
}

onMounted(load);
onActivated(load);
</script>

<template>
  <section class="page inventory-page">
    <div v-if="initialized" class="today-overview surface">
      <div><span>今日销售</span><strong>¥{{ formatMoney(overview.salesAmount) }}</strong></div>
      <div><span>今日采购</span><strong>¥{{ formatMoney(overview.purchaseAmount) }}</strong></div>
      <div><span>今日单据</span><strong>{{ overview.orderCount }} <small>笔</small></strong></div>
    </div>
    <van-search
      v-model="keyword"
      shape="round"
      background="transparent"
      placeholder="搜索编号、OE号、名称、拼音"
      @search="load"
      @clear="load"
      @update:model-value="load"
    />

    <button v-if="initialized" class="low-stock-banner" type="button" @click="showLowStock">
      <van-icon name="warning-o" />
      <span>{{ lowStockOnly ? "正在查看低库存零件" : `低库存提醒：${lowCount} 个配件库存不足` }}</span>
      <van-icon :name="lowStockOnly ? 'cross' : 'arrow'" />
    </button>

    <div v-if="!initialized" class="surface empty-state">
      <strong>这台手机还没有库存数据</strong>
      <p>请先与电脑配对并完成首次初始化。</p>
      <van-button type="primary" class="primary-action" block @click="router.push('/setup')">
        开始配对
      </van-button>
    </div>

    <div v-else class="inventory-list surface">
      <div class="list-head">
        <span>编号 / 名称</span><span>位置</span><span>数量</span><span>单位</span>
      </div>
      <button
        v-for="row in visibleRows"
        :key="row.part.id"
        class="inventory-row"
        type="button"
        @click="router.push(`/parts/${row.part.id}`)"
      >
        <span class="part-identity">
          <strong>{{ row.part.part_number }}</strong>
          <small>{{ row.part.name }}</small>
        </span>
        <span>{{ row.part.location || "—" }}</span>
        <span
          class="quantity"
          :class="{ low: row.displayQuantity < Number(row.part.min_stock) }"
        >
          {{ row.displayQuantity }}
        </span>
        <span class="unit">{{ row.part.unit }} <van-icon name="arrow" /></span>
      </button>
      <div v-if="rows.length > visibleRows.length" class="result-hint">
        当前展示前 {{ visibleRows.length }} 条，请输入编号、OE 号、名称或拼音继续缩小范围
      </div>
      <div v-if="!loading && !rows.length" class="empty-state">没有匹配的零件</div>
    </div>
  </section>
</template>

<style scoped>
.inventory-page :deep(.van-search) { padding: 4px 0 12px; }
.today-overview {
  display: grid;
  grid-template-columns: 1fr 1fr .75fr;
  margin-bottom: 10px;
  padding: 13px 6px;
}
.today-overview div { min-width: 0; padding: 0 9px; border-right: 1px solid #e4eaf1; }
.today-overview div:last-child { border-right: 0; }
.today-overview span,
.today-overview strong { display: block; }
.today-overview span { color: var(--muted); font-size: 10px; }
.today-overview strong { overflow: hidden; margin-top: 6px; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.today-overview small { font-size: 10px; font-weight: 500; }
.inventory-page :deep(.van-search__content) {
  padding: 5px 12px;
  background: white;
  border: 1px solid #cfd9e6;
  border-radius: 10px;
}
.low-stock-banner {
  width: 100%;
  min-height: 48px;
  margin-bottom: 12px;
  padding: 0 14px;
  display: grid;
  grid-template-columns: 20px 1fr 18px;
  align-items: center;
  gap: 8px;
  border: 0;
  border-radius: 10px;
  color: #eb6500;
  background: #fff7ed;
  text-align: left;
}
.inventory-list { overflow: hidden; }
.list-head, .inventory-row {
  display: grid;
  grid-template-columns: minmax(130px, 1.7fr) .8fr .55fr .55fr;
  align-items: center;
  gap: 8px;
}
.list-head {
  padding: 12px 12px 9px;
  color: #627087;
  font-size: 11px;
  border-bottom: 1px solid var(--border);
}
.inventory-row {
  width: 100%;
  min-height: 73px;
  padding: 10px 12px;
  border: 0;
  border-bottom: 1px solid #e8edf4;
  color: #1a2d45;
  background: white;
  text-align: left;
}
.inventory-row:last-child { border-bottom: 0; }
.part-identity strong, .part-identity small { display: block; }
.part-identity strong { margin-bottom: 4px; font-size: 14px; }
.part-identity small { overflow: hidden; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.unit { display: flex; align-items: center; justify-content: space-between; }
.result-hint { padding: 13px; color: #718197; background: #f8faff; font-size: 11px; text-align: center; }
</style>
