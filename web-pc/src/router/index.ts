import { createRouter, createWebHashHistory } from "vue-router";

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", component: () => import("../views/HomeView.vue"), meta: { title: "经营概览" } },
    { path: "/parts", component: () => import("../views/PartsView.vue"), meta: { title: "零件档案" } },
    { path: "/master-data", component: () => import("../views/MasterDataView.vue"), meta: { title: "基础资料" } },
    { path: "/purchase", component: () => import("../views/OrderView.vue"), meta: { title: "采购入库", kind: "purchase" } },
    { path: "/sales", component: () => import("../views/OrderView.vue"), meta: { title: "销售出库", kind: "sale" } },
    { path: "/inventory", component: () => import("../views/InventoryView.vue"), meta: { title: "库存查询" } },
    { path: "/stock-takes", component: () => import("../views/StockTakeView.vue"), meta: { title: "库存盘点" } },
    { path: "/reports", component: () => import("../views/ReportsView.vue"), meta: { title: "报表中心" } },
    { path: "/settings", component: () => import("../views/SettingsView.vue"), meta: { title: "系统设置" } },
  ],
});
