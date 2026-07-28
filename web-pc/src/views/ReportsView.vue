<script setup lang="ts">
import * as echarts from "echarts";
import { ElMessage } from "element-plus";
import { nextTick, onMounted, ref } from "vue";
import { http } from "../api";

const dashboard=ref<any>({trend:[]});
const rankings=ref<any>({parts:[],customers:[],suppliers:[]});
const trendChart=ref<HTMLElement>(), partChart=ref<HTMLElement>(), supplierChart=ref<HTMLElement>(), customerChart=ref<HTMLElement>();
const money=(value:number)=>`¥ ${(value/100).toLocaleString("zh-CN",{minimumFractionDigits:2})}`;
function download(){window.open("/api/excel/export/inventory")}
function downloadLedger(){window.open("/api/excel/export/ledger")}
function downloadSummary(){window.open("/api/excel/export/summary")}
async function reconcile(){
  const result:any=await http.get("/stock/reconcile");
  if(result.ok) ElMessage.success(`对账通过：已核对 ${result.checked_count} 个零件，库存快照与流水一致`);
  else ElMessage.error(`发现 ${result.mismatch_count} 个零件库存不一致，请先停止开单并检查`);
}
function barOption(rows:any[], nameKey:string, valueKey:string, color="#2f6bff") {
  const data=rows.slice(0,8).reverse();
  return {grid:{left:92,right:30,top:18,bottom:26},tooltip:{trigger:"axis"},xAxis:{type:"value",splitLine:{lineStyle:{color:"#edf0f5"}}},yAxis:{type:"category",data:data.map(row=>row[nameKey])},series:[{type:"bar",data:data.map(row=>row[valueKey]/100),itemStyle:{color,borderRadius:[0,4,4,0]},label:{show:true,position:"right"}}]};
}
onMounted(async()=>{
  dashboard.value=await http.get("/reports/dashboard");
  rankings.value=await http.get("/reports/rankings");
  await nextTick();
  echarts.init(trendChart.value!).setOption({grid:{left:55,right:20,top:28,bottom:32},legend:{data:["销售额","毛利"]},tooltip:{trigger:"axis"},xAxis:{type:"category",data:dashboard.value.trend.map((row:any)=>row.date.slice(5))},yAxis:{type:"value",splitLine:{lineStyle:{color:"#edf0f5"}}},series:[{name:"销售额",type:"line",smooth:true,data:dashboard.value.trend.map((row:any)=>row.sales/100),itemStyle:{color:"#2f6bff"}},{name:"毛利",type:"line",smooth:true,data:dashboard.value.trend.map((row:any)=>row.profit/100),itemStyle:{color:"#28a66a"}}]});
  echarts.init(partChart.value!).setOption(barOption(rankings.value.parts,"name","sales"));
  echarts.init(customerChart.value!).setOption(barOption(rankings.value.customers,"name","sales","#28a66a"));
  echarts.init(supplierChart.value!).setOption({tooltip:{trigger:"item"},legend:{bottom:0},series:[{type:"pie",radius:["42%","68%"],data:rankings.value.suppliers.slice(0,8).map((row:any)=>({name:row.name,value:row.purchases/100})),label:{formatter:"{b}\n{d}%"}}]});
});
</script>
<template>
  <div class="page-actions"><span>销售、毛利、商品、供应商与客户分析</span><div><el-button @click="reconcile">一键库存对账</el-button><el-button @click="downloadLedger">库存台账</el-button><el-button @click="downloadSummary">进销存汇总</el-button><el-button @click="download">库存报表</el-button></div></div>
  <div class="report-metrics"><div><span>近30天销售单</span><strong>{{dashboard.sales_order_count||0}}</strong></div><div><span>近30天采购单</span><strong>{{dashboard.purchase_order_count||0}}</strong></div><div><span>库存金额</span><strong>{{money(dashboard.inventory_amount||0)}}</strong></div></div>
  <section class="panel wide"><h3>销售趋势与毛利</h3><div ref="trendChart" class="chart"/></section>
  <div class="charts"><section class="panel"><h3>商品销售排行</h3><div ref="partChart" class="chart"/></section><section class="panel"><h3>供应商采购占比</h3><div ref="supplierChart" class="chart"/></section><section class="panel"><h3>客户销售排行</h3><div ref="customerChart" class="chart"/></section></div>
</template>
<style scoped>
.report-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:18px}.report-metrics>div{background:#fff;border:1px solid #e2e7ef;padding:18px;border-radius:8px}.report-metrics span,.report-metrics strong{display:block}.report-metrics span{color:#657186;margin-bottom:10px}.report-metrics strong{font-size:24px}.wide{margin-bottom:18px}.panel h3{font-size:15px;margin:0 0 12px}.chart{height:300px}.charts{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
</style>
