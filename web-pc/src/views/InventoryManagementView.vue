<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import InventoryView from "./InventoryView.vue";
import PartsView from "./PartsView.vue";
import StockTakeView from "./StockTakeView.vue";

type InventoryTab = "parts" | "stock" | "takes";

const route = useRoute();
const router = useRouter();
const tabs: Array<{ key: InventoryTab; label: string; description: string }> = [
  { key: "stock", label: "库存查询", description: "查询实时库存、平均成本、库存金额并追溯逐笔变化" },
  { key: "parts", label: "零件档案", description: "维护零件资料、价格与库存上下限" },
  { key: "takes", label: "库存盘点", description: "创建盘点单、录入实盘数量并过账" },
];
const views = {
  parts: PartsView,
  stock: InventoryView,
  takes: StockTakeView,
};

const activeTab = computed<InventoryTab>(() => {
  const tab = String(route.query.tab || "stock");
  return tab === "parts" || tab === "takes" ? tab : "stock";
});
const activeDescription = computed(
  () => tabs.find(tab => tab.key === activeTab.value)?.description,
);
const activeView = computed(() => views[activeTab.value]);

function switchTab(tab: InventoryTab) {
  void router.replace({
    path: "/inventory",
    query: tab === "stock" ? {} : { tab },
  });
}
</script>

<template>
  <section class="inventory-management">
    <div class="inventory-switcher">
      <div>
        <p class="eyebrow">库存工作台</p>
        <h2>库存管理</h2>
        <p>{{ activeDescription }}</p>
      </div>
      <el-button-group aria-label="库存功能切换">
        <el-button
          v-for="tab in tabs"
          :key="tab.key"
          :type="activeTab === tab.key ? 'primary' : 'default'"
          @click="switchTab(tab.key)"
        >
          {{ tab.label }}
        </el-button>
      </el-button-group>
    </div>
    <KeepAlive>
      <component :is="activeView" />
    </KeepAlive>
  </section>
</template>

<style scoped>
.inventory-management {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.inventory-switcher {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 18px 20px;
  background: #fff;
  border: 1px solid #e2e7ef;
  border-radius: 8px;
}
.inventory-switcher h2 {
  margin: 2px 0 7px;
  font-size: 22px;
}
.inventory-switcher p {
  margin: 0;
  color: #657186;
  font-size: 13px;
}
.inventory-switcher .eyebrow {
  color: #2f6bff;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1.4px;
}
@media (max-width: 900px) {
  .inventory-switcher {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
