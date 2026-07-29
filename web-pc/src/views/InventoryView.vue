<script setup lang="ts">
import { Clock, Document, Download, Refresh, Search } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { http } from "../api";
import { orderTypeLabel } from "../utils/order";

type StockHistory = {
  part: {
    id: string;
    part_number: string;
    name: string;
    unit: string;
    location?: string;
  };
  current_quantity: number;
  total: number;
  entries: any[];
};

const route = useRoute();
const router = useRouter();
const rows = ref<any[]>([]);
const keyword = ref("");
const statusFilter = ref("all");
const loading = ref(false);
const historyVisible = ref(false);
const historyLoading = ref(false);
const history = ref<StockHistory | null>(null);

const visibleRows = computed(() => {
  if (statusFilter.value === "all") return rows.value;
  return rows.value.filter(row => stockStatus(row).code === statusFilter.value);
});
const summary = computed(() => ({
  skuCount: rows.value.length,
  totalQuantity: rows.value.reduce((sum, row) => sum + Number(row.quantity || 0), 0),
  stockAmount: rows.value.reduce((sum, row) => sum + Number(row.stock_amount || 0), 0),
  warningCount: rows.value.filter(row =>
    ["negative", "low", "excess"].includes(stockStatus(row).code),
  ).length,
}));

const money = (value: number) =>
  `¥ ${(Number(value || 0) / 100).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
const quantity = (value: number) =>
  Number(value || 0).toLocaleString("zh-CN", { maximumFractionDigits: 3 });
const dateTime = (value: string) => {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value.replace("T", " ").slice(0, 19)
    : parsed.toLocaleString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      });
};

function stockStatus(row: any) {
  const current = Number(row.quantity || 0);
  if (current < 0) return { code: "negative", label: "负库存", type: "danger" as const };
  if (current === 0) return { code: "empty", label: "无库存", type: "info" as const };
  if (Number(row.min_stock || 0) > 0 && current <= Number(row.min_stock)) {
    return { code: "low", label: "库存不足", type: "warning" as const };
  }
  if (row.max_stock != null && current > Number(row.max_stock)) {
    return { code: "excess", label: "库存积压", type: "warning" as const };
  }
  return { code: "normal", label: "正常", type: "success" as const };
}

function changeTypeLabel(value: string) {
  return {
    purchase: "采购入库",
    purchase_return: "采购退货",
    sale: "销售出库",
    sale_return: "销售退货",
    adjust: "盘点调整",
    opening: "期初库存",
  }[value] || "其他变动";
}

function operationLabel(row: any) {
  if (row.source_type.includes("_void")) return "撤销回滚";
  if (row.source_type.includes("_reversal")) return "红冲";
  return "";
}

async function load() {
  loading.value = true;
  try {
    rows.value = (await http.get("/stock", {
      params: { keyword: keyword.value || undefined, limit: 1000 },
    })) as unknown as any[];
    const partId = String(route.query.part_id || "");
    if (partId && (!history.value || history.value.part.id !== partId)) {
      await openHistory(partId, false);
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "库存数据加载失败");
  } finally {
    loading.value = false;
  }
}

async function openHistory(partOrId: any, updateRoute = true) {
  const partId = typeof partOrId === "string" ? partOrId : partOrId.part_id;
  historyVisible.value = true;
  historyLoading.value = true;
  history.value = null;
  if (updateRoute && String(route.query.part_id || "") !== partId) {
    await router.replace({ query: { ...route.query, part_id: partId } });
  }
  try {
    history.value = (await http.get(`/stock/${partId}/history`, {
      params: { limit: 200 },
    })) as unknown as StockHistory;
  } catch (error) {
    historyVisible.value = false;
    ElMessage.error(error instanceof Error ? error.message : "库存变化记录加载失败");
  } finally {
    historyLoading.value = false;
  }
}

function clearHistoryRoute() {
  if (!route.query.part_id) return;
  const query = { ...route.query };
  delete query.part_id;
  void router.replace({ query });
}

function openDocument(row: any) {
  if (!row.document?.available) return;
  void router.push(`/orders/${row.document.kind}/${row.document.id}/print`);
}

function download() {
  window.open("/api/excel/export/inventory", "_blank");
}

watch(
  () => route.query.part_id,
  partId => {
    const value = String(partId || "");
    if (!value) {
      historyVisible.value = false;
      return;
    }
    if (!historyLoading.value && history.value?.part.id !== value) {
      void openHistory(value, false);
    }
  },
);
onMounted(() => void load());
</script>

<template>
  <div class="inventory-page">
    <div class="inventory-summary">
      <div>
        <span>零件种类</span>
        <strong>{{ summary.skuCount }}</strong>
        <small>当前查询结果</small>
      </div>
      <div>
        <span>库存总数量</span>
        <strong>{{ quantity(summary.totalQuantity) }}</strong>
        <small>所有单位数量合计</small>
      </div>
      <div>
        <span>库存金额</span>
        <strong>{{ money(summary.stockAmount) }}</strong>
        <small>按移动平均成本计算</small>
      </div>
      <div :class="{ warning: summary.warningCount }">
        <span>库存异常</span>
        <strong>{{ summary.warningCount }}</strong>
        <small>负库存、低库存或积压</small>
      </div>
    </div>

    <section class="panel inventory-panel">
      <div class="inventory-toolbar">
        <div class="search-group">
          <el-input
            v-model="keyword"
            clearable
            :prefix-icon="Search"
            placeholder="零件编号 / OE号 / 名称 / 拼音"
            @clear="load"
            @keyup.enter="load"
          />
          <el-select v-model="statusFilter" class="status-filter" aria-label="库存状态筛选">
            <el-option label="全部状态" value="all" />
            <el-option label="正常" value="normal" />
            <el-option label="无库存" value="empty" />
            <el-option label="库存不足" value="low" />
            <el-option label="库存积压" value="excess" />
            <el-option label="负库存" value="negative" />
          </el-select>
          <el-button type="primary" :icon="Search" @click="load">查询</el-button>
        </div>
        <div>
          <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
          <el-button :icon="Download" @click="download">导出 Excel</el-button>
        </div>
      </div>

      <el-table
        :data="visibleRows"
        v-loading="loading"
        stripe
        row-key="part_id"
        empty-text="没有找到符合条件的库存记录"
      >
        <el-table-column label="零件" min-width="230" fixed>
          <template #default="{ row }">
            <div class="part-cell">
              <strong>{{ row.part_number }}</strong>
              <span>{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="location" label="货位" min-width="105">
          <template #default="{ row }">{{ row.location || "—" }}</template>
        </el-table-column>
        <el-table-column label="当前库存" min-width="110" align="right">
          <template #default="{ row }">
            <strong :class="{ 'negative-number': row.quantity < 0 }" class="quantity-value">
              {{ quantity(row.quantity) }}
            </strong>
            <span class="unit-label">{{ row.unit }}</span>
          </template>
        </el-table-column>
        <el-table-column label="库存状态" min-width="105">
          <template #default="{ row }">
            <el-tag :type="stockStatus(row).type" effect="light" size="small">
              {{ stockStatus(row).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="库存范围" min-width="115" align="right">
          <template #default="{ row }">
            {{ quantity(row.min_stock) }} ~ {{ row.max_stock == null ? "不限" : quantity(row.max_stock) }}
          </template>
        </el-table-column>
        <el-table-column label="平均成本" min-width="120" align="right">
          <template #default="{ row }"><span class="money">{{ money(row.avg_cost) }}</span></template>
        </el-table-column>
        <el-table-column label="库存金额" min-width="130" align="right">
          <template #default="{ row }"><span class="money">{{ money(row.stock_amount) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="116" fixed="right" align="right">
          <template #default="{ row }">
            <el-button link type="primary" :icon="Clock" @click="openHistory(row)">
              变化记录
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-footer">显示 {{ visibleRows.length }} / {{ rows.length }} 种零件</div>
    </section>

    <el-drawer
      v-model="historyVisible"
      class="history-drawer"
      size="860px"
      :with-header="false"
      destroy-on-close
      @closed="clearHistoryRoute"
    >
      <div v-loading="historyLoading" class="history-content">
        <header class="history-header">
          <div>
            <p>库存变化记录</p>
            <h3 v-if="history">{{ history.part.part_number }} · {{ history.part.name }}</h3>
            <span v-if="history">
              货位 {{ history.part.location || "未设置" }} · 共 {{ history.total }} 条流水
            </span>
          </div>
          <div v-if="history" class="current-stock">
            <span>当前库存</span>
            <strong>{{ quantity(history.current_quantity) }}</strong>
            <small>{{ history.part.unit }}</small>
          </div>
        </header>

        <el-alert
          :closable="false"
          type="info"
          show-icon
          title="库存流水为只读记录；“查看单据”会打开现有采购/销售单据打印预览。"
        />

        <el-table
          v-if="history"
          :data="history.entries"
          class="history-table"
          row-key="id"
          empty-text="该零件还没有库存变化记录"
        >
          <el-table-column label="发生时间" width="145">
            <template #default="{ row }">
              <span class="date-time">{{ dateTime(row.occurred_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="业务" min-width="116">
            <template #default="{ row }">
              <strong class="change-label">{{ changeTypeLabel(row.change_type) }}</strong>
              <el-tag v-if="operationLabel(row)" effect="plain" size="small">
                {{ operationLabel(row) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="变动" width="92" align="right">
            <template #default="{ row }">
              <strong :class="row.quantity > 0 ? 'stock-in' : 'stock-out'" class="change-quantity">
                {{ row.quantity > 0 ? "+" : "" }}{{ quantity(row.quantity) }}
              </strong>
            </template>
          </el-table-column>
          <el-table-column label="变动后库存" width="112" align="right">
            <template #default="{ row }">{{ quantity(row.balance_after) }}</template>
          </el-table-column>
          <el-table-column label="单位成本" width="110" align="right">
            <template #default="{ row }">{{ money(row.unit_cost) }}</template>
          </el-table-column>
          <el-table-column label="来源单据" min-width="190">
            <template #default="{ row }">
              <template v-if="row.document">
                <div class="document-cell">
                  <span>{{ orderTypeLabel(row.document.order_type) }}</span>
                  <el-button
                    v-if="row.document.available"
                    link
                    type="primary"
                    :icon="Document"
                    @click="openDocument(row)"
                  >
                    {{ row.document.order_no }}
                  </el-button>
                  <small v-else>{{ row.document.order_no }} · 已撤销</small>
                </div>
              </template>
              <span v-else class="source-note">{{ row.remark || "系统库存记录" }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.inventory-page { display: flex; flex-direction: column; gap: 16px; }
.inventory-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.inventory-summary > div { padding: 16px 18px; background: #fff; border: 1px solid #e2e7ef; border-radius: 8px; }
.inventory-summary > div.warning { border-color: #f4d29b; background: #fffdfa; }
.inventory-summary span, .inventory-summary strong, .inventory-summary small { display: block; }
.inventory-summary span { color: #667388; font-size: 12px; }
.inventory-summary strong { margin: 7px 0 5px; color: #172033; font-size: 21px; font-variant-numeric: tabular-nums; }
.inventory-summary .warning strong { color: #b86d00; }
.inventory-summary small { color: #929cab; font-size: 11px; }
.inventory-panel { padding: 0; overflow: hidden; }
.inventory-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 16px; border-bottom: 1px solid #e9edf3; }
.inventory-toolbar > div, .search-group { display: flex; align-items: center; gap: 8px; }
.search-group .el-input { width: 340px; }
.status-filter { width: 132px; }
.part-cell strong, .part-cell span { display: block; }
.part-cell strong { color: #253047; font-size: 13px; }
.part-cell span { margin-top: 3px; color: #8994a5; font-size: 12px; }
.quantity-value, .money { font-variant-numeric: tabular-nums; }
.unit-label { margin-left: 4px; color: #929cab; font-size: 12px; }
.negative-number { color: #d64242; }
.table-footer { padding: 11px 16px; color: #8994a5; font-size: 12px; text-align: right; border-top: 1px solid #eef1f5; }
.history-content { min-height: 100%; padding: 24px; }
.history-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; padding-bottom: 18px; border-bottom: 1px solid #e8ecf2; margin-bottom: 16px; }
.history-header p { margin: 0 0 7px; color: #2f6bff; font-size: 12px; font-weight: 700; letter-spacing: 1.2px; }
.history-header h3 { margin: 0 0 7px; color: #172033; font-size: 20px; }
.history-header > div > span { color: #7b8798; font-size: 12px; }
.current-stock { min-width: 130px; padding-left: 22px; text-align: right; border-left: 1px solid #e2e7ef; }
.current-stock span, .current-stock strong, .current-stock small { display: block; }
.current-stock span, .current-stock small { color: #7b8798; font-size: 12px; }
.current-stock strong { margin: 5px 0 2px; color: #172033; font-size: 27px; font-variant-numeric: tabular-nums; }
.history-table { margin-top: 16px; }
.date-time { color: #657186; font-size: 12px; font-variant-numeric: tabular-nums; }
.change-label { display: block; margin-bottom: 4px; color: #344056; font-size: 12px; }
.change-quantity { font-variant-numeric: tabular-nums; }
.stock-in { color: #16885a; }
.stock-out { color: #d34f4f; }
.document-cell span, .document-cell small { display: block; }
.document-cell span, .document-cell small, .source-note { color: #8a95a6; font-size: 11px; }
.document-cell .el-button { height: auto; padding: 2px 0 0; font-size: 12px; }
:global(.history-drawer) { max-width: 100vw; }
@media (max-width: 1080px) {
  .inventory-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .inventory-toolbar { align-items: flex-start; flex-direction: column; }
}
@media (max-width: 760px) {
  .inventory-summary { grid-template-columns: 1fr; }
  .search-group { align-items: stretch; flex-direction: column; width: 100%; }
  .search-group .el-input, .status-filter { width: 100%; }
}
</style>
