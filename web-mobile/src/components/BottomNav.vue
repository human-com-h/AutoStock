<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();
const active = computed({
  get: () => {
    const name = String(route.name || "inventory");
    if (name.startsWith("purchase")) return "purchase";
    if (name.startsWith("sale")) return "sale";
    if (name.startsWith("records") || name === "order-detail") return "records";
    if (
      name.startsWith("profile") ||
      name === "setup" ||
      name === "sync" ||
      name === "contacts"
    ) return "profile";
    return "inventory";
  },
  set: (value: string) => router.push({ name: value }),
});
</script>

<template>
  <van-tabbar v-model="active" route class="bottom-nav" active-color="#1677ff">
    <van-tabbar-item name="inventory" to="/" icon="wap-home-o">库存</van-tabbar-item>
    <van-tabbar-item name="purchase" to="/purchase" icon="down">入库</van-tabbar-item>
    <van-tabbar-item name="sale" to="/sale" icon="upgrade">出库</van-tabbar-item>
    <van-tabbar-item name="records" to="/records" icon="orders-o">记录</van-tabbar-item>
    <van-tabbar-item name="profile" to="/profile" icon="contact-o">我的</van-tabbar-item>
  </van-tabbar>
</template>
