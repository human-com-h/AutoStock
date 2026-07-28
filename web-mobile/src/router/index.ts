import { createRouter, createWebHashHistory } from "vue-router";

const router = createRouter({
  history: createWebHashHistory("/m/"),
  routes: [
    {
      path: "/",
      name: "inventory",
      component: () => import("../views/HomeView.vue"),
      meta: { title: "AutoStock" },
    },
    {
      path: "/parts/:id",
      name: "part-detail",
      component: () => import("../views/PartDetailView.vue"),
      meta: { title: "零件详情" },
    },
    {
      path: "/purchase",
      name: "purchase",
      component: () => import("../views/QuickOrderView.vue"),
      props: { kind: "purchase" },
      meta: { title: "快速入库" },
    },
    {
      path: "/sale",
      name: "sale",
      component: () => import("../views/QuickOrderView.vue"),
      props: { kind: "sale" },
      meta: { title: "快速出库" },
    },
    {
      path: "/records",
      name: "records",
      component: () => import("../views/RecordsView.vue"),
      meta: { title: "近期记录" },
    },
    {
      path: "/profile",
      name: "profile",
      component: () => import("../views/ProfileView.vue"),
      meta: { title: "我的" },
    },
    {
      path: "/sync",
      name: "sync",
      component: () => import("../views/SyncCenterView.vue"),
      meta: { title: "同步中心" },
    },
    {
      path: "/setup",
      name: "setup",
      component: () => import("../views/SetupView.vue"),
    },
  ],
});

export default router;
