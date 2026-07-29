<script setup lang="ts">
import * as echarts from "echarts";
import {
  Checked,
  Download,
  Refresh,
  TrendCharts,
} from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { http } from "../api";

const days = ref(30);
const loading = ref(false);
const reconciling = ref(false);
const reconcileVisible = ref(false);
const reconcileResult = ref<any>({ ok: true, differences: [] });
const dashboard = ref<any>({ trend: [] });
const rankings = ref<any>({ parts: [], customers: [], suppliers: [] });
const trendElement = ref<HTMLElement>();
const partElement = ref<HTMLElement>();
const supplierElement = ref<HTMLElement>();
const customerElement = ref<HTMLElement>();
const chartInstances: echarts.ECharts[] = [];
let resizeObserver: ResizeObserver | undefined;

const money = (value: number) =>
  `¥ ${(Number(value || 0) / 100).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
const quantity = (value: number) =>
  Number(value || 0).toLocaleString("zh-CN", { maximumFractionDigits: 3 });
const periodLabel = computed(() => `近 ${days.value} 天`);
const reportRange = computed(() => {
  if (!dashboard.value.period_start || !dashboard.value.period_end) return "";
  return `${dashboard.value.period_start} 至 ${dashboard.value.period_end}`;
});
const metricCards = computed(() => [
  {
    label: `${periodLabel.value}销售额`,
    value: money(dashboard.value.period_sales),
    hint: `${dashboard.value.sales_order_count || 0} 张销售类单据`,
    tone: "blue",
  },
  {
    label: `${periodLabel.value}毛利`,
    value: money(dashboard.value.period_profit),
    hint: `毛利率 ${(dashboard.value.gross_margin || 0).toFixed(1)}%`,
    tone: "green",
  },
  {
    label: `${periodLabel.value}采购额`,
    value: money(dashboard.value.period_purchase_amount),
    hint: `${dashboard.value.purchase_order_count || 0} 张采购类单据`,
    tone: "amber",
  },
  {
    label: "当前库存金额",
    value: money(dashboard.value.inventory_amount),
    hint: "按实时库存 × 移动平均成本",
    tone: "slate",
  },
]);

function noDataGraphic(hasData: boolean, text = "当前范围暂无数据") {
  return hasData
    ? []
    : [
        {
          type: "text",
          left: "center",
          top: "middle",
          style: { text, fill: "#9aa5b5", fontSize: 14 },
        },
      ];
}

function baseTooltip() {
  return {
    trigger: "axis",
    backgroundColor: "#172033",
    borderWidth: 0,
    textStyle: { color: "#fff" },
  };
}

function renderCharts() {
  if (!trendElement.value || !partElement.value || !supplierElement.value || !customerElement.value) {
    return;
  }
  chartInstances.splice(0).forEach(instance => instance.dispose());
  const trendChart = echarts.init(trendElement.value);
  const partChart = echarts.init(partElement.value);
  const supplierChart = echarts.init(supplierElement.value);
  const customerChart = echarts.init(customerElement.value);
  chartInstances.push(trendChart, partChart, supplierChart, customerChart);

  const trend = dashboard.value.trend || [];
  const trendHasData = trend.some((row: any) => row.sales || row.profit);
  trendChart.setOption({
    animationDuration: 450,
    color: ["#2f6bff", "#23a36d"],
    grid: { left: 60, right: 24, top: 48, bottom: 34 },
    legend: { top: 5, right: 0, itemWidth: 18, itemHeight: 8 },
    tooltip: {
      ...baseTooltip(),
      valueFormatter: (value: unknown) => money(Number(value) * 100),
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: trend.map((row: any) => row.date.slice(5)),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: "#d9e0ea" } },
      axisLabel: { color: "#7b8798", interval: trend.length > 40 ? 8 : trend.length > 20 ? 4 : 0 },
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
        showSymbol: false,
        data: trend.map((row: any) => row.sales / 100),
        lineStyle: { width: 2.5 },
        areaStyle: { color: "rgba(47,107,255,.08)" },
      },
      {
        name: "毛利",
        type: "line",
        smooth: 0.35,
        showSymbol: false,
        data: trend.map((row: any) => row.profit / 100),
        lineStyle: { width: 2.5 },
      },
    ],
    graphic: noDataGraphic(trendHasData),
  });

  const parts = (rankings.value.parts || []).slice(0, 8).reverse();
  partChart.setOption({
    color: ["#2f6bff"],
    grid: { left: 110, right: 58, top: 18, bottom: 30 },
    tooltip: {
      ...baseTooltip(),
      valueFormatter: (value: unknown) => money(Number(value) * 100),
    },
    xAxis: {
      type: "value",
      axisLabel: { color: "#7b8798" },
      splitLine: { lineStyle: { color: "#edf0f5" } },
    },
    yAxis: {
      type: "category",
      data: parts.map((row: any) => row.name),
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: { width: 95, overflow: "truncate", color: "#56647a" },
    },
    series: [
      {
        type: "bar",
        barMaxWidth: 15,
        data: parts.map((row: any) => row.sales / 100),
        itemStyle: { borderRadius: [0, 3, 3, 0] },
        label: {
          show: true,
          position: "right",
          color: "#667388",
          formatter: ({ value }: any) => `¥${Number(value).toLocaleString("zh-CN")}`,
        },
      },
    ],
    graphic: noDataGraphic(parts.length > 0),
  });

  const suppliers = (rankings.value.suppliers || []).slice(0, 7);
  supplierChart.setOption({
    color: ["#2f6bff", "#23a36d", "#f3a83b", "#7b61d1", "#42a5b3", "#d86b7c", "#8a97a8"],
    tooltip: {
      trigger: "item",
      backgroundColor: "#172033",
      borderWidth: 0,
      textStyle: { color: "#fff" },
      formatter: (params: any) => `${params.name}<br/>${money(params.value * 100)} · ${params.percent}%`,
    },
    legend: {
      type: "scroll",
      bottom: 0,
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: "#667388" },
    },
    series: [
      {
        type: "pie",
        radius: ["48%", "70%"],
        center: ["50%", "43%"],
        avoidLabelOverlap: true,
        data: suppliers.map((row: any) => ({
          name: row.name,
          value: row.purchases / 100,
        })),
        itemStyle: { borderColor: "#fff", borderWidth: 2 },
        label: { show: false },
        emphasis: { label: { show: true, formatter: "{d}%", fontSize: 15, fontWeight: 700 } },
      },
    ],
    graphic: noDataGraphic(suppliers.length > 0),
  });

  const customers = (rankings.value.customers || []).slice(0, 8).reverse();
  customerChart.setOption({
    color: ["#23a36d"],
    grid: { left: 105, right: 58, top: 18, bottom: 30 },
    tooltip: {
      ...baseTooltip(),
      valueFormatter: (value: unknown) => money(Number(value) * 100),
    },
    xAxis: {
      type: "value",
      axisLabel: { color: "#7b8798" },
      splitLine: { lineStyle: { color: "#edf0f5" } },
    },
    yAxis: {
      type: "category",
      data: customers.map((row: any) => row.name),
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: { width: 90, overflow: "truncate", color: "#56647a" },
    },
    series: [
      {
        type: "bar",
        barMaxWidth: 15,
        data: customers.map((row: any) => row.sales / 100),
        itemStyle: { borderRadius: [0, 3, 3, 0] },
        label: {
          show: true,
          position: "right",
          color: "#667388",
          formatter: ({ value }: any) => `¥${Number(value).toLocaleString("zh-CN")}`,
        },
      },
    ],
    graphic: noDataGraphic(customers.length > 0),
  });
}

async function load() {
  loading.value = true;
  try {
    const [dashboardData, rankingData] = await Promise.all([
      http.get("/reports/dashboard", { params: { days: days.value } }),
      http.get("/reports/rankings", { params: { days: days.value } }),
    ]);
    dashboard.value = dashboardData;
    rankings.value = rankingData;
    await nextTick();
    renderCharts();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "报表数据加载失败");
  } finally {
    loading.value = false;
  }
}

async function reconcile() {
  reconciling.value = true;
  try {
    reconcileResult.value = await http.get("/stock/reconcile");
    if (reconcileResult.value.ok) {
      ElMessage.success(`对账通过：${reconcileResult.value.checked_count} 个零件库存一致`);
    } else {
      reconcileVisible.value = true;
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "库存对账失败");
  } finally {
    reconciling.value = false;
  }
}

function exportFile(path: string) {
  window.open(path, "_blank");
}

onMounted(() => {
  void load();
  resizeObserver = new ResizeObserver(() => chartInstances.forEach(instance => instance.resize()));
  [trendElement, partElement, supplierElement, customerElement].forEach(element => {
    if (element.value) resizeObserver?.observe(element.value);
  });
});
onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  chartInstances.splice(0).forEach(instance => instance.dispose());
});
</script>

<template>
  <div class="reports-page" v-loading="loading">
    <header class="report-header">
      <div>
        <p class="eyebrow">经营分析</p>
        <h2>报表中心</h2>
        <p>{{ reportRange || "按业务日期汇总销售、毛利、采购与往来排名" }}</p>
      </div>
      <div class="report-controls">
        <el-radio-group v-model="days" @change="load">
          <el-radio-button :value="7">近 7 天</el-radio-button>
          <el-radio-button :value="30">近 30 天</el-radio-button>
          <el-radio-button :value="90">近 90 天</el-radio-button>
        </el-radio-group>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      </div>
    </header>

    <div class="report-toolbar">
      <div>
        <el-button type="primary" plain :icon="Checked" :loading="reconciling" @click="reconcile">
          库存对账
        </el-button>
        <span class="toolbar-hint">对比库存快照与库存流水汇总，不修改数据</span>
      </div>
      <el-dropdown trigger="click">
        <el-button :icon="Download">导出报表</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="exportFile('/api/excel/export/inventory')">
              库存报表
            </el-dropdown-item>
            <el-dropdown-item @click="exportFile('/api/excel/export/ledger')">
              库存台账
            </el-dropdown-item>
            <el-dropdown-item @click="exportFile('/api/excel/export/summary')">
              进销存汇总
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <div class="report-metrics">
      <article v-for="item in metricCards" :key="item.label" :class="item.tone">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <small>{{ item.hint }}</small>
      </article>
    </div>

    <section class="panel trend-panel">
      <div class="section-heading">
        <div>
          <h3>销售与毛利趋势</h3>
          <p>退货与红冲按反方向计入，日期空档补零展示。</p>
        </div>
        <el-icon><TrendCharts /></el-icon>
      </div>
      <div ref="trendElement" class="trend-chart" />
    </section>

    <div class="ranking-grid">
      <section class="panel">
        <div class="section-heading">
          <div>
            <h3>零件销售额排行</h3>
            <p>{{ periodLabel }}销售净额前 8 名</p>
          </div>
        </div>
        <div ref="partElement" class="ranking-chart" />
      </section>
      <section class="panel">
        <div class="section-heading">
          <div>
            <h3>供应商采购占比</h3>
            <p>{{ periodLabel }}采购净额前 7 名</p>
          </div>
        </div>
        <div ref="supplierElement" class="ranking-chart" />
      </section>
      <section class="panel">
        <div class="section-heading">
          <div>
            <h3>客户销售额排行</h3>
            <p>{{ periodLabel }}销售净额前 8 名</p>
          </div>
        </div>
        <div ref="customerElement" class="ranking-chart" />
      </section>
    </div>

    <section class="panel detail-panel">
      <div class="section-heading">
        <div>
          <h3>零件销售明细</h3>
          <p>图表用于比较，表格保留精确数量、销售额与毛利。</p>
        </div>
      </div>
      <el-table :data="rankings.parts" empty-text="当前范围暂无零件销售数据">
        <el-table-column type="index" label="#" width="52" />
        <el-table-column prop="name" label="零件名称" min-width="210" />
        <el-table-column label="销售数量" align="right" min-width="110">
          <template #default="{ row }">{{ quantity(row.quantity) }}</template>
        </el-table-column>
        <el-table-column label="销售额" align="right" min-width="135">
          <template #default="{ row }"><span class="money">{{ money(row.sales) }}</span></template>
        </el-table-column>
        <el-table-column label="毛利" align="right" min-width="135">
          <template #default="{ row }">
            <span :class="{ negative: row.profit < 0 }" class="money">{{ money(row.profit) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="毛利率" align="right" min-width="105">
          <template #default="{ row }">
            {{ row.sales ? `${((row.profit / row.sales) * 100).toFixed(1)}%` : "—" }}
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="reconcileVisible" title="发现库存不一致" width="760px">
      <el-alert
        :closable="false"
        type="error"
        show-icon
        title="请暂停开单并核查以下零件，系统未自动修改任何业务数据。"
      />
      <el-table :data="reconcileResult.differences" class="reconcile-table">
        <el-table-column prop="part_number" label="零件编号" min-width="130" />
        <el-table-column prop="name" label="零件名称" min-width="150" />
        <el-table-column prop="ledger_quantity" label="流水汇总" align="right" />
        <el-table-column prop="snapshot_quantity" label="库存快照" align="right" />
        <el-table-column label="差异" align="right">
          <template #default="{ row }">
            <span class="negative">{{ quantity(row.difference) }}</span>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button type="primary" @click="reconcileVisible = false">我知道了</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.reports-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.report-header,
.report-controls,
.report-toolbar,
.report-toolbar > div,
.section-heading {
  display: flex;
  align-items: center;
}
.report-header,
.report-toolbar,
.section-heading {
  justify-content: space-between;
}
.report-header {
  gap: 24px;
}
.report-header h2 {
  margin: 2px 0 8px;
  color: #172033;
  font-size: 24px;
}
.report-header p,
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
.report-controls {
  gap: 10px;
  flex-shrink: 0;
}
.report-toolbar {
  min-height: 52px;
  padding: 8px 10px 8px 14px;
  background: #fff;
  border: 1px solid #e2e7ef;
  border-radius: 8px;
}
.report-toolbar > div {
  gap: 12px;
}
.toolbar-hint {
  color: #8994a5;
  font-size: 12px;
}
.report-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}
.report-metrics article {
  position: relative;
  overflow: hidden;
  padding: 20px;
  background: #fff;
  border: 1px solid #e2e7ef;
  border-radius: 10px;
}
.report-metrics article::before {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 3px;
  background: #8a97a8;
  content: "";
}
.report-metrics article.blue::before { background: #2f6bff; }
.report-metrics article.green::before { background: #23a36d; }
.report-metrics article.amber::before { background: #f3a83b; }
.report-metrics span,
.report-metrics strong,
.report-metrics small {
  display: block;
}
.report-metrics span {
  color: #667388;
  font-size: 13px;
}
.report-metrics strong {
  margin: 10px 0 8px;
  color: #172033;
  font-size: 24px;
  font-variant-numeric: tabular-nums;
}
.report-metrics small {
  color: #929cab;
  font-size: 12px;
}
.section-heading {
  gap: 16px;
  margin-bottom: 10px;
}
.section-heading h3 {
  margin: 0 0 5px;
  font-size: 15px;
}
.section-heading > .el-icon {
  color: #2f6bff;
  font-size: 22px;
}
.trend-chart {
  height: 320px;
}
.ranking-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}
.ranking-chart {
  height: 300px;
}
.detail-panel {
  padding-bottom: 12px;
}
.money {
  font-variant-numeric: tabular-nums;
}
.negative {
  color: #d64242;
  font-weight: 600;
}
.reconcile-table {
  margin-top: 16px;
}
@media (max-width: 1240px) {
  .report-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .ranking-grid { grid-template-columns: 1fr 1fr; }
  .ranking-grid > :last-child { grid-column: 1 / -1; }
}
@media (max-width: 1050px) {
  .report-header { align-items: flex-start; flex-direction: column; }
  .report-controls { flex-wrap: wrap; }
  .ranking-grid { grid-template-columns: 1fr; }
  .ranking-grid > :last-child { grid-column: auto; }
}
@media (max-width: 820px) {
  .ranking-grid { grid-template-columns: 1fr; }
  .ranking-grid > :last-child { grid-column: auto; }
  .toolbar-hint { display: none; }
}
</style>
