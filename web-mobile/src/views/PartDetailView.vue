<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { getPartWithStock, recentPartLedgers, type PartWithStock } from "../services/inventory";
import type { StockLedgerRow } from "../db/schema";

const route = useRoute();
const router = useRouter();
const row = ref<PartWithStock | null>(null);
const ledgers = ref<StockLedgerRow[]>([]);

onMounted(async () => {
  const partId = String(route.params.id);
  [row.value, ledgers.value] = await Promise.all([
    getPartWithStock(partId),
    recentPartLedgers(partId),
  ]);
});

function ledgerLabel(type: string): string {
  return (
    {
      purchase: "采购入库",
      sale: "销售出库",
      purchase_return: "采购退货",
      sale_return: "销售退货",
      adjust: "盘点调整",
      opening: "期初库存",
    }[type] || type
  );
}
</script>

<template>
  <section v-if="row" class="page detail-page">
    <button class="back-link" type="button" @click="router.back()">
      <van-icon name="arrow-left" /> 返回库存
    </button>
    <div class="part-hero surface">
      <div>
        <span>{{ row.part.part_number }}</span>
        <h2>{{ row.part.name }}</h2>
        <p>{{ row.part.spec || "暂无规格" }} · {{ row.part.location || "未设置货位" }}</p>
      </div>
      <div class="hero-stock">
        <small>当前库存</small>
        <strong>{{ row.displayQuantity }} {{ row.part.unit }}</strong>
      </div>
    </div>
    <div class="stock-note">
      库存 {{ row.displayQuantity }}
      <template v-if="row.pendingQuantity">
        （含本机未同步 {{ row.pendingQuantity > 0 ? "+" : "" }}{{ row.pendingQuantity }}）
      </template>
      ，服务器数据截至 {{ row.snapshot?.updated_at?.slice(11, 16) || "尚未同步" }}
    </div>
    <div class="price-grid">
      <div><small>参考进价</small><strong>¥{{ (row.part.purchase_price / 100).toFixed(2) }}</strong></div>
      <div><small>建议售价</small><strong>¥{{ (row.part.sale_price / 100).toFixed(2) }}</strong></div>
    </div>
    <h3 class="section-title">最近出入库</h3>
    <div class="surface ledger-list">
      <div v-for="ledger in ledgers" :key="ledger.id" class="ledger-row">
        <div>
          <strong>{{ ledgerLabel(ledger.change_type) }}</strong>
          <small>{{ ledger.occurred_at.replace("T", " ").slice(0, 16) }}</small>
        </div>
        <span :class="{ inbound: ledger.quantity > 0 }">
          {{ ledger.quantity > 0 ? "+" : "" }}{{ ledger.quantity }}
        </span>
      </div>
      <div v-if="!ledgers.length" class="empty-state">近 90 天暂无出入库记录</div>
    </div>
  </section>
</template>

<style scoped>
.back-link { margin: 0 0 10px; border: 0; color: #53708e; background: transparent; }
.part-hero { display: flex; align-items: center; justify-content: space-between; padding: 18px; }
.part-hero span { color: var(--blue); font-size: 13px; font-weight: 700; }
.part-hero h2 { margin: 5px 0; font-size: 20px; }
.part-hero p { margin: 0; color: var(--muted); font-size: 12px; }
.hero-stock { text-align: right; }
.hero-stock small, .hero-stock strong { display: block; }
.hero-stock small { margin-bottom: 6px; color: var(--muted); }
.hero-stock strong { color: var(--blue); font-size: 18px; }
.stock-note { margin: 10px 2px 18px; color: #64758b; font-size: 12px; }
.price-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.price-grid div { padding: 15px; border-radius: 10px; background: #eaf3ff; }
.price-grid small, .price-grid strong { display: block; }
.price-grid small { color: #63748b; }
.price-grid strong { margin-top: 6px; font-size: 18px; }
.ledger-row { display: flex; justify-content: space-between; padding: 14px 16px; border-bottom: 1px solid #edf1f6; }
.ledger-row:last-child { border-bottom: 0; }
.ledger-row small { display: block; margin-top: 4px; color: var(--muted); }
.ledger-row > span { align-self: center; color: #d94b43; font-weight: 750; }
.ledger-row > span.inbound { color: #16944b; }
</style>
