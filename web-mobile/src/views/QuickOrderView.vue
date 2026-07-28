<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { showFailToast, showSuccessToast } from "vant";
import { db, type NamedRow } from "../db/schema";
import { getPartWithStock, searchLocalParts, type PartWithStock } from "../services/inventory";
import { createQuickOrder, type OrderKind } from "../services/orders";
import { useAppStore } from "../stores/app";

const props = defineProps<{ kind: OrderKind }>();
const appStore = useAppStore();
const keyword = ref("");
const matches = ref<PartWithStock[]>([]);
const selected = ref<PartWithStock | null>(null);
const quantity = ref(1);
const priceYuan = ref("");
const partnerId = ref("");
const partnerName = ref("");
const partners = ref<NamedRow[]>([]);
const saving = ref(false);
const isPurchase = computed(() => props.kind === "purchase");

async function search(): Promise<void> {
  matches.value = keyword.value ? (await searchLocalParts(keyword.value)).slice(0, 8) : [];
}

async function choose(row: PartWithStock): Promise<void> {
  selected.value = row;
  keyword.value = `${row.part.part_number} · ${row.part.name}`;
  matches.value = [];
  priceYuan.value = ((isPurchase.value ? row.part.purchase_price : row.part.sale_price) / 100).toFixed(2);
}

async function save(): Promise<void> {
  if (!selected.value) {
    showFailToast("请先选择零件");
    return;
  }
  const price = Math.round(Number(priceYuan.value) * 100);
  if (!Number.isFinite(price) || price < 0) {
    showFailToast("请输入正确价格");
    return;
  }
  saving.value = true;
  try {
    const result = await createQuickOrder({
      kind: props.kind,
      partId: selected.value.part.id,
      quantity: quantity.value,
      price,
      partnerId: partnerId.value || null,
      partnerName: partnerName.value || null,
    });
    showSuccessToast(result.uploaded ? "已保存，电脑端可见" : "已离线保存，等待同步");
    await appStore.refreshPending();
    selected.value = await getPartWithStock(selected.value.part.id);
    quantity.value = 1;
  } catch (error) {
    showFailToast(error instanceof Error ? error.message : "保存失败");
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  partners.value = isPurchase.value ? await db.suppliers.toArray() : await db.customers.toArray();
});
</script>

<template>
  <section class="page quick-order">
    <label class="field-label">配件搜索 / 选择</label>
    <van-search
      v-model="keyword"
      class="part-search"
      placeholder="搜索编号、OE号、名称、拼音"
      @update:model-value="search"
    />
    <div v-if="matches.length" class="search-results surface">
      <button v-for="row in matches" :key="row.part.id" type="button" @click="choose(row)">
        <span><strong>{{ row.part.part_number }}</strong>{{ row.part.name }}</span>
        <small>库存 {{ row.displayQuantity }} {{ row.part.unit }}</small>
      </button>
    </div>

    <div v-if="selected" class="selected-part surface">
      <div>
        <strong>{{ selected.part.part_number }}</strong>
        <span>{{ selected.part.name }}</span>
      </div>
      <div><small>当前库存</small><strong class="quantity">{{ selected.displayQuantity }} {{ selected.part.unit }}</strong></div>
    </div>

    <label class="field-label">{{ isPurchase ? "入库数量" : "出库数量" }}</label>
    <van-stepper v-model="quantity" min="0.001" step="1" input-width="calc(100vw - 142px)" button-size="48" />

    <label class="field-label">单位{{ isPurchase ? "进" : "售" }}价（元）</label>
    <van-field v-model="priceYuan" type="number" placeholder="0.00" class="form-field" />

    <label class="field-label">{{ isPurchase ? "供应商（可选）" : "客户（可选）" }}</label>
    <select v-model="partnerId" class="native-select">
      <option value="">请选择</option>
      <option v-for="partner in partners" :key="partner.id" :value="partner.id">{{ partner.name }}</option>
    </select>
    <van-field
      v-if="!isPurchase"
      v-model="partnerName"
      class="form-field customer-name"
      placeholder="散客可直接填写客户名称"
    />

    <van-button
      type="primary"
      block
      class="primary-action save-button"
      :loading="saving"
      @click="save"
    >
      保存{{ isPurchase ? "入库" : "出库" }}单
    </van-button>
    <p class="offline-copy">无论是否连接电脑，单据都会先完整保存到本机。</p>
  </section>
</template>

<style scoped>
.field-label { display: block; margin: 15px 2px 8px; font-size: 14px; font-weight: 650; }
.part-search { padding: 0; background: transparent; }
.part-search :deep(.van-search__content), .form-field, .native-select {
  border: 1px solid #ccd7e5;
  border-radius: 10px;
  background: white;
}
.part-search :deep(.van-search__content) { min-height: 48px; }
.search-results { position: absolute; z-index: 9; left: 14px; right: 14px; overflow: hidden; }
.search-results button {
  width: 100%; padding: 12px 14px; display: flex; justify-content: space-between;
  border: 0; border-bottom: 1px solid #edf1f5; background: white; text-align: left;
}
.search-results span strong { display: block; }
.search-results small { color: var(--muted); }
.selected-part { margin-top: 12px; padding: 15px; display: flex; justify-content: space-between; }
.selected-part span, .selected-part small { display: block; margin-top: 5px; color: var(--muted); }
.selected-part > div:last-child { text-align: right; }
.quick-order :deep(.van-stepper) { display: flex; }
.quick-order :deep(.van-stepper__input) { flex: 1; height: 48px; font-size: 22px; font-weight: 700; }
.quick-order :deep(.van-stepper__minus), .quick-order :deep(.van-stepper__plus) { color: var(--blue); background: white; border: 1px solid #ccd7e5; }
.form-field { min-height: 48px; }
.native-select { width: 100%; height: 48px; padding: 0 14px; color: #233750; }
.customer-name { margin-top: 8px; }
.save-button { margin-top: 28px; }
.offline-copy { text-align: center; color: var(--muted); font-size: 11px; }
</style>
