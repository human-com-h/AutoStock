<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { showFailToast, showSuccessToast } from "vant";
import { useRouter } from "vue-router";
import { db, type NamedRow } from "../db/schema";
import { searchLocalParts, type PartWithStock } from "../services/inventory";
import { createQuickOrder, type OrderKind } from "../services/orders";
import { useAppStore } from "../stores/app";

interface CartLine {
  part: PartWithStock;
  quantity: number;
  priceYuan: string;
  remark: string;
}

const props = defineProps<{ kind: OrderKind }>();
const router = useRouter();
const appStore = useAppStore();
const keyword = ref("");
const matches = ref<PartWithStock[]>([]);
const cart = ref<CartLine[]>([]);
const partnerId = ref("");
const partnerName = ref("");
const orderRemark = ref("");
const partners = ref<NamedRow[]>([]);
const saving = ref(false);
const isPurchase = computed(() => props.kind === "purchase");
const totalAmount = computed(() =>
  cart.value.reduce(
    (total, line) =>
      total + Math.round(line.quantity * Number(line.priceYuan || 0) * 100),
    0,
  ),
);

async function search(): Promise<void> {
  matches.value = keyword.value
    ? (await searchLocalParts(keyword.value)).slice(0, 8)
    : [];
}

function choose(row: PartWithStock): void {
  const existing = cart.value.find((line) => line.part.part.id === row.part.id);
  if (existing) {
    existing.quantity += 1;
    showSuccessToast("数量已增加");
  } else {
    cart.value.push({
      part: row,
      quantity: 1,
      priceYuan: (
        (isPurchase.value ? row.part.purchase_price : row.part.sale_price) / 100
      ).toFixed(2),
      remark: "",
    });
  }
  keyword.value = "";
  matches.value = [];
}

function removeLine(index: number): void {
  cart.value.splice(index, 1);
}

async function save(): Promise<void> {
  if (!cart.value.length) {
    showFailToast("请至少添加一个零件");
    return;
  }
  const items = cart.value.map((line) => ({
    partId: line.part.part.id,
    quantity: Number(line.quantity),
    price: Math.round(Number(line.priceYuan) * 100),
    remark: line.remark || null,
  }));
  if (
    items.some(
      (item) =>
        !Number.isFinite(item.quantity) ||
        item.quantity <= 0 ||
        !Number.isFinite(item.price) ||
        item.price < 0,
    )
  ) {
    showFailToast("请检查数量和价格");
    return;
  }

  saving.value = true;
  try {
    const selectedPartner = partners.value.find((row) => row.id === partnerId.value);
    const result = await createQuickOrder({
      kind: props.kind,
      items,
      partnerId: partnerId.value || null,
      partnerName:
        partnerName.value.trim() || (!isPurchase.value ? selectedPartner?.name : null),
      remark: orderRemark.value.trim() || null,
    });
    showSuccessToast(result.uploaded ? "已保存，电脑端可见" : "已离线保存，等待同步");
    await appStore.refreshPending();
    cart.value = [];
    orderRemark.value = "";
    await router.push(`/records/${props.kind}/${result.orderId}`);
  } catch (error) {
    showFailToast(error instanceof Error ? error.message : "保存失败");
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  partners.value = isPurchase.value
    ? await db.suppliers.toArray()
    : await db.customers.toArray();
});
</script>

<template>
  <section class="page quick-order">
    <div class="order-intro">
      <div>
        <strong>{{ isPurchase ? "采购入库" : "销售出库" }}</strong>
        <span>可连续添加多个配件，合并保存为一张单据</span>
      </div>
      <em>{{ cart.length }} 项</em>
    </div>

    <label class="field-label">添加配件</label>
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

    <div v-if="cart.length" class="surface order-lines">
      <div v-for="(line, index) in cart" :key="line.part.part.id" class="order-line">
        <div class="line-title">
          <div>
            <strong>{{ line.part.part.part_number }}</strong>
            <span>{{ line.part.part.name }}</span>
          </div>
          <button type="button" aria-label="删除配件" @click="removeLine(index)">
            <van-icon name="delete-o" />
          </button>
        </div>
        <div class="line-controls">
          <label>
            <span>数量（{{ line.part.part.unit }}）</span>
            <van-stepper
              v-model="line.quantity"
              min="0.001"
              step="1"
              input-width="52"
              button-size="34"
            />
          </label>
          <label>
            <span>单价（元）</span>
            <input v-model="line.priceYuan" type="number" inputmode="decimal" />
          </label>
        </div>
      </div>
    </div>
    <div v-else class="surface empty-cart">
      <van-icon name="orders-o" />
      <span>搜索并点选配件后，会在这里汇总</span>
    </div>

    <label class="field-label">{{ isPurchase ? "供应商（可选）" : "客户（可选）" }}</label>
    <select v-model="partnerId" class="native-select">
      <option value="">请选择</option>
      <option v-for="partner in partners" :key="partner.id" :value="partner.id">
        {{ partner.name }}
      </option>
    </select>
    <van-field
      v-if="!isPurchase"
      v-model="partnerName"
      class="form-field customer-name"
      placeholder="散客可直接填写客户名称"
    />

    <label class="field-label">整单备注（可选）</label>
    <van-field
      v-model="orderRemark"
      class="form-field"
      type="textarea"
      rows="2"
      maxlength="100"
      show-word-limit
      placeholder="例如：送货、加急、核对后签收"
    />

    <div class="order-total">
      <span>共 {{ cart.length }} 项</span>
      <strong>合计 ¥{{ (totalAmount / 100).toFixed(2) }}</strong>
    </div>
    <van-button
      type="primary"
      block
      class="primary-action save-button"
      :loading="saving"
      :disabled="!cart.length"
      @click="save"
    >
      保存{{ isPurchase ? "入库" : "出库" }}单
    </van-button>
    <p class="offline-copy">无论是否连接电脑，整张单据都会先完整保存到本机。</p>
  </section>
</template>

<style scoped>
.order-intro {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 5px 2px 2px;
}
.order-intro strong,
.order-intro span {
  display: block;
}
.order-intro strong {
  font-size: 18px;
}
.order-intro span {
  margin-top: 5px;
  color: var(--muted);
  font-size: 11px;
}
.order-intro em {
  min-width: 48px;
  padding: 7px 10px;
  border-radius: 9px;
  color: var(--blue);
  background: #eaf3ff;
  font-size: 12px;
  font-style: normal;
  font-weight: 700;
  text-align: center;
}
.field-label {
  display: block;
  margin: 15px 2px 8px;
  font-size: 14px;
  font-weight: 650;
}
.part-search {
  padding: 0;
  background: transparent;
}
.part-search :deep(.van-search__content),
.form-field,
.native-select {
  border: 1px solid #ccd7e5;
  border-radius: 10px;
  background: white;
}
.part-search :deep(.van-search__content) {
  min-height: 48px;
}
.search-results {
  position: absolute;
  z-index: 9;
  right: 14px;
  left: 14px;
  overflow: hidden;
}
.search-results button {
  display: flex;
  width: 100%;
  justify-content: space-between;
  padding: 12px 14px;
  border: 0;
  border-bottom: 1px solid #edf1f5;
  background: white;
  text-align: left;
}
.search-results span strong {
  display: block;
}
.search-results small {
  color: var(--muted);
}
.order-lines {
  margin-top: 12px;
  overflow: hidden;
}
.order-line {
  padding: 14px;
  border-bottom: 1px solid #e8edf4;
}
.order-line:last-child {
  border-bottom: 0;
}
.line-title,
.line-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.line-title strong,
.line-title span {
  display: block;
}
.line-title strong {
  color: var(--blue);
  font-size: 13px;
}
.line-title span {
  margin-top: 4px;
  font-weight: 650;
}
.line-title button {
  width: 38px;
  height: 38px;
  flex: none;
  border: 0;
  color: #d95850;
  background: transparent;
  font-size: 20px;
}
.line-controls {
  margin-top: 13px;
}
.line-controls label {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
}
.line-controls label > span {
  color: var(--muted);
  font-size: 11px;
}
.line-controls input {
  width: 82px;
  height: 36px;
  padding: 0 8px;
  border: 1px solid #cdd8e5;
  border-radius: 7px;
  color: #22364f;
  text-align: right;
}
.empty-cart {
  display: flex;
  min-height: 90px;
  align-items: center;
  justify-content: center;
  gap: 9px;
  margin-top: 12px;
  color: var(--muted);
  font-size: 12px;
}
.empty-cart .van-icon {
  color: #97a9bd;
  font-size: 22px;
}
.form-field {
  min-height: 48px;
}
.native-select {
  width: 100%;
  height: 48px;
  padding: 0 14px;
  color: #233750;
}
.customer-name {
  margin-top: 8px;
}
.order-total {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 20px;
  padding: 14px 2px 4px;
  border-top: 1px solid #dbe3ee;
  color: var(--muted);
}
.order-total strong {
  color: #172d47;
  font-size: 20px;
}
.save-button {
  margin-top: 14px;
}
.offline-copy {
  color: var(--muted);
  font-size: 11px;
  text-align: center;
}
</style>
