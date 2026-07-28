import { createRouter, createWebHashHistory } from "vue-router";

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", component: () => import("../views/HomeView.vue"), meta: { title: "经营概览" } },
    { path: "/parts", redirect: { path: "/inventory", query: { tab: "parts" } } },
    { path: "/master-data", component: () => import("../views/MasterDataView.vue"), meta: { title: "基础资料" } },
    { path: "/purchase", component: () => import("../views/OrderView.vue"), meta: { title: "采购入库", kind: "purchase" } },
    { path: "/sales", component: () => import("../views/OrderView.vue"), meta: { title: "销售出库", kind: "sale" } },
    { path: "/inventory", component: () => import("../views/InventoryManagementView.vue"), meta: { title: "库存管理" } },
    { path: "/stock-takes", redirect: { path: "/inventory", query: { tab: "takes" } } },
    { path: "/reports", component: () => import("../views/ReportsView.vue"), meta: { title: "报表中心" } },
    { path: "/sync", component: () => import("../views/SyncView.vue"), meta: { title: "设备与同步" } },
    { path: "/settings", component: () => import("../views/SettingsView.vue"), meta: { title: "系统设置" } },
  ],
});
