<script setup lang="ts">
import { onMounted, ref } from "vue"; import { http } from "../api";
const rows=ref<any[]>([]), keyword=ref(""), loading=ref(false);
async function load(){loading.value=true;try{rows.value=await http.get("/stock",{params:{keyword:keyword.value||undefined}})}finally{loading.value=false}}
onMounted(load);
</script>
<template><div class="page-actions"><el-input v-model="keyword" clearable placeholder="编号 / OE号 / 名称 / 拼音" style="width:360px" @keyup.enter="load"/><el-button type="primary" @click="load">查询</el-button></div>
<div class="panel"><el-table :data="rows" v-loading="loading" stripe><el-table-column prop="part_number" label="零件编号"/><el-table-column prop="name" label="零件名称"/><el-table-column prop="location" label="货位"/><el-table-column prop="quantity" label="库存"/><el-table-column prop="unit" label="单位"/><el-table-column label="平均成本"><template #default="{row}">¥ {{(row.avg_cost/100).toFixed(2)}}</template></el-table-column><el-table-column label="库存金额"><template #default="{row}">¥ {{(row.stock_amount/100).toFixed(2)}}</template></el-table-column></el-table></div></template>
