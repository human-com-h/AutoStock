<script setup lang="ts">
import * as echarts from "echarts";
import { computed, nextTick, onMounted, ref } from "vue";
import { http } from "../api";

const alerts = ref<any[]>([]);
const sales = ref<any[]>([]);
const purchases = ref<any[]>([]);
const chart = ref<HTMLElement>();
const today = new Date().toISOString().slice(0, 10);
const todaySales = computed(() => sales.value.filter(x => x.order_date === today && x.order_type === "sale"));
const revenue = computed(() => todaySales.value.reduce((sum, x) => sum + x.total_amount, 0));
const profit = computed(() => todaySales.value.reduce((sum, x) => sum + x.total_amount - x.items.reduce((n:any, i:any) => n + i.cost_amount, 0), 0));
const money = (v:number) => `¥ ${(v / 100).toLocaleString("zh-CN", { minimumFractionDigits: 2 })}`;

onMounted(async () => {
  const data = await Promise.all([
    http.get("/stock/alerts"), http.get("/orders/sales"), http.get("/orders/purchases"),
  ]);
  alerts.value = data[0] as unknown as any[];
  sales.value = data[1] as unknown as any[];
  purchases.value = data[2] as unknown as any[];
  await nextTick();
  const totals = Array.from({ length: 30 }, (_, index) => {
    const date = new Date(); date.setDate(date.getDate() - (29 - index));
    const key = date.toISOString().slice(0, 10);
    return sales.value.filter(x => x.order_date === key && x.order_type === "sale").reduce((n, x) => n + x.total_amount / 100, 0);
  });
  echarts.init(chart.value!).setOption({
    grid:{left:42,right:16,top:20,bottom:28}, tooltip:{trigger:"axis"},
    xAxis:{type:"category",data:Array.from({length:30},(_,i)=>i+1),axisLine:{lineStyle:{color:"#d9e0ea"}}},
    yAxis:{type:"value",splitLine:{lineStyle:{color:"#edf0f5"}}},
    series:[{type:"line",data:totals,smooth:true,symbolSize:5,lineStyle:{color:"#2f6bff",width:2},itemStyle:{color:"#2f6bff"},areaStyle:{color:"rgba(47,107,255,.06)"}}],
  });
});
</script>
<template>
  <div class="metrics">
    <div><span>今日销售额</span><strong>{{ money(revenue) }}</strong></div>
    <div><span>今日毛利</span><strong>{{ money(profit) }}</strong></div>
    <div><span>待补货</span><strong class="warn">{{ alerts.filter(x=>x.alerts.includes("low")).length }}</strong></div>
    <div><span>负库存</span><strong class="warn">{{ alerts.filter(x=>x.alerts.includes("negative")).length }}</strong></div>
  </div>
  <section class="panel trend"><h3>近30天销售趋势</h3><div ref="chart" class="chart" /></section>
  <div class="home-grid">
    <section class="panel"><h3>库存预警</h3><el-table :data="alerts.slice(0,6)">
      <el-table-column prop="part_number" label="零件编号"/><el-table-column prop="name" label="零件名称"/>
      <el-table-column prop="quantity" label="当前库存"/><el-table-column label="预警类型"><template #default="{row}">{{ row.alerts.join(" / ") }}</template></el-table-column>
    </el-table></section>
    <section class="panel"><h3>最近单据</h3><el-table :data="[...sales,...purchases].sort((a,b)=>b.created_at?.localeCompare(a.created_at)).slice(0,6)">
      <el-table-column prop="order_type" label="类型"/><el-table-column prop="order_no" label="单据编号"/>
      <el-table-column prop="order_date" label="日期"/><el-table-column label="金额"><template #default="{row}">{{ money(row.total_amount) }}</template></el-table-column>
    </el-table></section>
  </div>
</template>
<style scoped>
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:18px}.metrics>div{background:#fff;border:1px solid #e2e7ef;border-radius:8px;padding:20px}.metrics span{display:block;color:#5f6b7d;font-size:14px;margin-bottom:17px}.metrics strong{font-size:28px;color:#2f6bff}.metrics .warn{color:#f26b21}.trend{margin-bottom:18px}.panel h3{margin:0 0 16px;font-size:15px}.chart{height:265px}.home-grid{display:grid;grid-template-columns:1fr 1.4fr;gap:18px}
</style>
