<script setup lang="ts">
import {
  Box,
  DataAnalysis,
  Document,
  Goods,
  HomeFilled,
  Operation,
  Sell,
  Setting,
  ShoppingCart,
} from "@element-plus/icons-vue";

const nav = [
  ["/", "经营概览", HomeFilled],
  ["/parts", "零件档案", Goods],
  ["/purchase", "采购入库", ShoppingCart],
  ["/sales", "销售出库", Sell],
  ["/inventory", "库存查询", Box],
  ["/stock-takes", "库存盘点", Operation],
  ["/reports", "报表中心", DataAnalysis],
  ["/settings", "系统设置", Setting],
];
</script>

<template>
  <el-container class="app-shell">
    <el-aside width="220px" class="sidebar">
      <div class="brand"><Document /> AutoStock <span>汽配库存</span></div>
      <el-menu router :default-active="$route.path" class="nav">
        <el-menu-item v-for="[path, label, icon] in nav" :key="String(path)" :index="String(path)">
          <el-icon><component :is="icon" /></el-icon><span>{{ label }}</span>
        </el-menu-item>
      </el-menu>
      <div class="connection"><i /> 本地数据 · 已连接</div>
    </el-aside>
    <el-container>
      <el-header class="topbar">
        <strong>{{ $route.meta.title || "经营概览" }}</strong>
        <span>{{ new Date().toLocaleDateString("zh-CN", { dateStyle: "long" }) }}</span>
      </el-header>
      <el-main class="workspace"><router-view /></el-main>
    </el-container>
  </el-container>
</template>

<style>
:root { font-family: Inter, "Microsoft YaHei", sans-serif; color:#172033; background:#f5f7fb; }
* { box-sizing:border-box; } body { margin:0; } .app-shell { min-height:100vh; }
.sidebar { position:relative; background:#10243e; color:#fff; }
.brand { height:72px; display:flex; align-items:center; gap:8px; padding:0 20px; font-size:18px; font-weight:700; }
.brand svg { width:22px; } .brand span { font-size:13px; font-weight:500; opacity:.72; }
.nav { border:0!important; background:transparent!important; }
.nav .el-menu-item { color:#c8d4e5; margin:4px 10px; border-radius:7px; height:48px; }
.nav .el-menu-item:hover { background:#173556; color:#fff; }
.nav .el-menu-item.is-active { color:#fff; background:#2f6bff; }
.connection { position:absolute; bottom:28px; left:20px; font-size:12px; color:#b7c6d9; }
.connection i { display:inline-block; width:8px; height:8px; border-radius:50%; background:#3ddc84; margin-right:7px; }
.topbar { height:72px; display:flex; align-items:center; justify-content:space-between; background:#fff; border-bottom:1px solid #e5eaf2; padding:0 28px; }
.topbar strong { font-size:21px; } .topbar span { color:#657186; font-size:13px; }
.workspace { padding:24px 28px; background:#f5f7fb; }
.page-actions { display:flex; gap:10px; justify-content:space-between; margin-bottom:18px; }
.panel { background:#fff; border:1px solid #e2e7ef; border-radius:8px; padding:20px; }
.money { font-variant-numeric:tabular-nums; }
</style>
