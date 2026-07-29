<script setup lang="ts">
import * as echarts from "echarts";
import {
  Box,
  DataAnalysis,
  Money,
  Printer,
  Sell,
  ShoppingCart,
  TrendCharts,
  Warning,
} from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { http } from "../api";
import { orderTypeLabel } from "../utils/order";

type DashboardData = {
  today_sales: number;
  today_profit: number;
  low_stock_count: number;
  negative_stock_count: number;
  inventory_amount: number;
  trend: Array<{ date: string; sales: number; profit: number }>;
  alerts: any[];
  recent_orders: any[];
};

const router = useRouter();
const loading = ref(false);
const chartElement = ref<HTMLElement>();
const dashboard = ref<DashboardData>({
  today_sales: 0,
  today_profit: 0,
  low_stock_count: 0,
  negative_stock_count: 0,
  inventory_amount: 0,
  trend: [],
  alerts: [],
  recent_orders: [],
});
let trendChart: echarts.ECharts | undefined;
let resizeObserver: ResizeObserver | undefined;

const money = (value: number) =>
  `¥ ${(value / 100).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
const quantity = (value: number) =>
  Number(value || 0).toLocaleString("zh-CN", { maximumFractionDigits: 3 });
const todayProfitRate = computed(() =>
  dashboard.value.today_sales > 0
    ? (dashboard.value.today_profit / dashboard.value.today_sales) * 100
    : null,
);
const kpis = computed(() => [
  {
    label: "今日销售额",
    value: money(dashboard.value.today_sales),
    hint: "已扣除今日销售退货",
    tone: "blue",
    icon: Money,
  },
  {
    label: "今日毛利",
    value: money(dashboard.value.today_profit),
    hint:
      todayProfitRate.value == null
        ? "毛利率 —"
        : `毛利率 ${todayProfitRate.value.toFixed(1)}%`,
    tone: "green",
    icon: TrendCharts,
  },
  {
    label: "待补货零件",
    value: String(dashboard.value.low_stock_count),
    hint: "库存低于或等于下限",
    tone: dashboard.value.low_stock_count ? "amber" : "slate",
    icon: Warning,
  },
  {
    label: "负库存零件",
    value: String(dashboard.value.negative_stock_count),
    hint: dashboard.value.negative_stock_count ? "建议优先核查流水" : "当前库存状态正常",
    tone: dashboard.value.negative_stock_count ? "red" : "slate",
    icon: Box,
  },
]);
const alertRows = computed(() =>
  [...dashboard.value.alerts]
    .sort((left, right) => {
      const priority = (row: any) =>
        row.alerts.includes("negative") ? 0 : row.alerts.includes("low") ? 1 : 2;
      return priority(left) - priority(right);
    })
    .slice(0, 6),
);

function alertLabel(code: string) {
  return {
    negative: "负库存",
    low: "库存不足",
    excess: "库存积压",
    stale: "长期未动销",
  }[code] || code;
}

function alertType(code: string): "danger" | "warning" | "info" {
  if (code === "negative") return "danger";
  if (code === "low" || code === "excess") return "warning";
  return "info";
}

function renderTrend() {
  if (!chartElement.value) return;
  trendChart ||= echarts.init(chartElement.value);
  const rows = dashboard.value.trend;
  const hasData = rows.some(row => row.sales !== 0 || row.profit !== 0);
  trendChart.setOption(
    {
      animationDuration: 450,
      color: ["#2f6bff", "#23a36d"],
      grid: { left: 58, right: 24, top: 44, bottom: 34 },
      legend: { top: 4, right: 0, itemWidth: 18, itemHeight: 8 },
      tooltip: {
        trigger: "axis",
        backgroundColor: "#172033",
        borderWidth: 0,
        textStyle: { color: "#fff" },
        valueFormatter: (value: unknown) => money(Number(value) * 100),
      },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: rows.map(row => row.date.slice(5)),
        axisTick: { show: false },
        axisLine: { lineStyle: { color: "#d9e0ea" } },
        axisLabel: { color: "#7b8798", interval: rows.length > 20 ? 4 : "auto" },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          color: "#7b8798",
          formatter: (value: number) => `¥${value >= 10000 ? `${(value / 10000).toFixed(1)}万` : value}`,
        },
        splitLine: { lineStyle: { color: "#edf0f5" } },
      },
      series: [
        {
          name: "销售额",
          type: "line",
          smooth: 0.35,
          symbol: "circle",
          symbolSize: 6,
          showSymbol: false,
          data: rows.map(row => row.sales / 100),
          lineStyle: { width: 2.5 },
          areaStyle: { color: "rgba(47,107,255,.08)" },
        },
        {
          name: "毛利",
          type: "line",
          smooth: 0.35,
          symbol: "circle",
          symbolSize: 6,
          showSymbol: false,
          data: rows.map(row => row.profit / 100),
          lineStyle: { width: 2.5 },
        },
      ],
      graphic: hasData
        ? []
        : [
            {
              type: "text",
              left: "center",
              top: "middle",
              style: { text: "近 30 天暂无销售数据", fill: "#9aa5b5", fontSize: 14 },
            },
          ],
    },
    true,
  );
}

async function load() {
  loading.value = true;
  try {
    dashboard.value = (await http.get("/reports/dashboard", {
      params: { days: 30 },
    })) as unknown as DashboardData;
    await nextTick();
    renderTrend();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "概览数据加载失败");
  } finally {
    loading.value = false;
  }
}

function openInventoryHistory(row: any) {
  void router.push({ path: "/inventory", query: { part_id: row.part_id } });
}

function previewOrder(row: any) {
  void router.push(`/orders/${row.kind}/${row.id}/print`);
}

onMounted(() => {
  void load();
  if (chartElement.value) {
    resizeObserver = new ResizeObserver(() => trendChart?.resize());
    resizeObserver.observe(chartElement.value);
  }
});
onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  trendChart?.dispose();
});
</script>

<template>
  <div class="overview-page" v-loading="loading">
    <header class="overview-header">
      <div>
        <p class="eyebrow">经营驾驶舱</p>
        <h2>今天的经营情况，一眼看清</h2>
        <p>销售与毛利已计入退货影响，库存数据来自实时库存流水。</p>
      </div>
      <div class="quick-actions" aria-label="常用功能">
        <el-button :icon="ShoppingCart" @click="router.push('/purchase')">采购入库</el-button>
        <el-button :icon="Sell" @click="router.push('/sales')">销售出库</el-button>
        <el-button type="primary" :icon="DataAnalysis" @click="router.push('/reports')">
          查看报表
        </el-button>
      </div>
    </header>

    <div class="metric-grid">
      <article v-for="item in kpis" :key="item.label" class="metric-card">
        <div class="metric-icon" :class="item.tone">
          <el-icon><component :is="item.icon" /></el-icon>
        </div>
        <div>
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <small>{{ item.hint }}</small>
        </div>
      </article>
    </div>

    <section class="panel trend-panel">
      <div class="section-heading">
        <div>
          <h3>近 30 天销售与毛利趋势</h3>
          <p>按业务日期汇总，销售退货按反方向抵减。</p>
        </div>
        <div class="inventory-value">
          <span>当前库存金额</span>
          <strong>{{ money(dashboard.inventory_amount) }}</strong>
        </div>
      </div>
      <div ref="chartElement" class="trend-chart" />
    </section>

    <div class="overview-grid">
      <section class="panel">
        <div class="section-heading">
          <div>
            <h3>库存提醒</h3>
            <p>优先展示负库存与低库存零件。</p>
          </div>
          <el-button link type="primary" @click="router.push('/inventory')">查看全部</el-button>
        </div>
        <el-table :data="alertRows" empty-text="当前没有库存预警">
          <el-table-column label="零件" min-width="180">
            <template #default="{ row }">
              <div class="part-cell">
                <strong>{{ row.part_number }}</strong>
                <span>{{ row.name }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="库存" width="92" align="right">
            <template #default="{ row }">{{ quantity(row.quantity) }}</template>
          </el-table-column>
          <el-table-column label="状态" min-width="150">
            <template #default="{ row }">
              <el-tag
                v-for="code in row.alerts.slice(0, 2)"
                :key="code"
                :type="alertType(code)"
                effect="light"
                size="small"
              >
                {{ alertLabel(code) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column width="74" align="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openInventoryHistory(row)">追溯</el-button>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <section class="panel">
        <div class="section-heading">
          <div>
            <h3>最近业务单据</h3>
            <p>采购、销售与退货单据按创建时间排序。</p>
          </div>
        </div>
        <el-table :data="dashboard.recent_orders" empty-text="暂无业务单据">
          <el-table-column label="单据" min-width="185">
            <template #default="{ row }">
              <div class="part-cell">
                <strong>{{ row.order_no }}</strong>
                <span>{{ orderTypeLabel(row.order_type) }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="order_date" label="日期" width="110" />
          <el-table-column label="金额" min-width="120" align="right">
            <template #default="{ row }">
              <span class="money">{{ money(row.total_amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column width="90" align="right">
            <template #default="{ row }">
              <el-button link type="primary" :icon="Printer" @click="previewOrder(row)">
                单据
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </section>
    </div>
  </div>
</template>

<style scoped>
.overview-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.overview-header,
.section-heading,
.quick-actions {
  display: flex;
  align-items: center;
}
.overview-header {
  justify-content: space-between;
  gap: 24px;
}
.overview-header h2 {
  margin: 2px 0 8px;
  color: #172033;
  font-size: 24px;
  letter-spacing: -0.4px;
}
.overview-header p,
.section-heading p {
  margin: 0;
  color: #778397;
  font-size: 13px;
}
.eyebrow {
  color: #2f6bff !important;
  font-weight: 700;
  letter-spacing: 1.6px;
}
.quick-actions {
  gap: 8px;
  flex-shrink: 0;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}
.metric-card {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  min-height: 132px;
  padding: 20px;
  background: #fff;
  border: 1px solid #e2e7ef;
  border-radius: 10px;
}
.metric-icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  flex: 0 0 40px;
  color: #56647a;
  background: #eef1f5;
  border-radius: 8px;
}
.metric-icon.blue { color: #2f6bff; background: #edf3ff; }
.metric-icon.green { color: #16885a; background: #eaf8f2; }
.metric-icon.amber { color: #b86d00; background: #fff5df; }
.metric-icon.red { color: #d64242; background: #fff0f0; }
.metric-card span,
.metric-card strong,
.metric-card small {
  display: block;
}
.metric-card span {
  color: #667388;
  font-size: 13px;
}
.metric-card strong {
  margin: 8px 0 7px;
  color: #172033;
  font-size: 26px;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.metric-card small {
  color: #929cab;
  font-size: 12px;
}
.section-heading {
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 14px;
}
.section-heading h3 {
  margin: 0 0 5px;
  font-size: 15px;
}
.inventory-value {
  text-align: right;
}
.inventory-value span,
.inventory-value strong {
  display: block;
}
.inventory-value span {
  color: #8893a4;
  font-size: 12px;
}
.inventory-value strong {
  margin-top: 4px;
  color: #172033;
  font-size: 18px;
  font-variant-numeric: tabular-nums;
}
.trend-chart {
  height: 300px;
}
.overview-grid {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.2fr);
  gap: 18px;
}
.part-cell strong,
.part-cell span {
  display: block;
}
.part-cell strong {
  color: #253047;
  font-size: 13px;
}
.part-cell span {
  margin-top: 3px;
  color: #8994a5;
  font-size: 12px;
}
.el-tag + .el-tag {
  margin-left: 5px;
}
@media (max-width: 1180px) {
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .overview-grid { grid-template-columns: 1fr; }
}
@media (max-width: 1050px) {
  .overview-header { align-items: flex-start; flex-direction: column; }
  .quick-actions { width: 100%; flex-wrap: wrap; }
}
@media (max-width: 760px) {
  .metric-grid { grid-template-columns: 1fr; }
}
</style>
