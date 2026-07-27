import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory("/m/"),
  routes: [
    {
      path: "/",
      name: "home",
      component: () => import("../views/HomeView.vue"),
    },
  ],
});

export default router;
