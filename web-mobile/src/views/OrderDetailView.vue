<script setup lang="ts">
import { computed, onActivated, onMounted, ref } from "vue";
import { showFailToast, showSuccessToast } from "vant";
import { useRoute, useRouter } from "vue-router";
import {
  getLocalOrderDetail,
  type LocalOrderDetail,
  type OrderKind,
} from "../services/orders";
import { formatMoney, formatQuantity } from "../utils/print";

const route = useRoute();
const router = useRouter();
const detail = ref<LocalOrderDetail | null>(null);
const loading = ref(true);
const kind = computed<OrderKind>(() =>
  route.params.kind === "purchase" ? "purchase" : "sale",
);
const isPurchase = computed(() => kind.value === "purchase");
const partnerTitle = computed(() => (isPurchase.value ? "供应商" : "客户"));
const partnerName = computed(() => {
  if (!detail.value) return "散客 / 未填写";
  if (!isPurchase.value && "customer_name" in detail.value.order) {
    return detail.value.order.customer_name || detail.value.partner?.name || "散客 / 未填写";
  }
  return detail.value.partner?.name || "未填写";
});

function partnerField(key: string): string {
  const value = detail.value?.partner?.[key];
  return typeof value === "string" ? value : "";
}

function linePrice(line: LocalOrderDetail["lines"][number]): number {
  return "purchase_price" in line.item ? line.item.purchase_price : line.item.sale_price;
}

async function load(): Promise<void> {
  loading.value = true;
  detail.value = await getLocalOrderDetail(kind.value, String(route.params.id));
  loading.value = false;
}

function buildShareText(): string {
  if (!detail.value) return "";
  const title = isPurchase.value ? "采购入库单" : "销售出库单";
  const lines = detail.value.lines.map(
    (line, index) =>
      `${index + 1}. ${line.part?.name || "未知零件"} × ${formatQuantity(line.item.quantity)} ${line.part?.unit || ""}，¥${formatMoney(line.item.amount)}`,
  );
  return [
    `${title} ${detail.value.order.order_no}`,
    `日期：${detail.value.order.order_date}`,
    `${partnerTitle.value}：${partnerName.value}`,
    ...lines,
    `合计：¥${formatMoney(detail.value.order.total_amount)}`,
    detail.value.order.remark ? `备注：${detail.value.order.remark}` : "",
  ]
    .filter(Boolean)
    .join("\n");
}

async function shareOrder(): Promise<void> {
  const text = buildShareText();
  if (!text) return;
  try {
    if (navigator.share) {
      await navigator.share({
        title: `${isPurchase.value ? "采购入库单" : "销售出库单"} ${detail.value?.order.order_no}`,
        text,
      });
      return;
    }
    await navigator.clipboard.writeText(text);
    showSuccessToast("单据内容已复制");
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") return;
    showFailToast("分享失败，请稍后重试");
  }
}

function openPrintPreview(): void {
  router.push(`/records/${kind.value}/${route.params.id}/print`);
}

onMounted(load);
onActivated(load);
</script>

<template>
  <section class="page order-detail-page">
    <div v-if="detail" class="order-heading">
      <div>
        <span>{{ isPurchase ? "采购入库单" : "销售出库单" }}</span>
        <strong>{{ detail.order.order_no }}</strong>
      </div>
      <em :class="{ pending: detail.order.sync_status === 'pending' }">
        {{ detail.order.sync_status === "pending" ? "待同步" : "已入账" }}
      </em>
    </div>

    <template v-if="detail">
      <div class="surface summary-card">
        <div><span>单据日期</span><strong>{{ detail.order.order_date }}</strong></div>
        <div><span>{{ partnerTitle }}</span><strong>{{ partnerName }}</strong></div>
        <div v-if="partnerField('contact')"><span>联系人</span><strong>{{ partnerField("contact") }}</strong></div>
        <div v-if="partnerField('phone')"><span>联系电话</span><strong>{{ partnerField("phone") }}</strong></div>
        <div v-if="partnerField('address') || partnerField('location')" class="wide">
          <span>联系地址</span>
          <strong>{{ partnerField("address") || partnerField("location") }}</strong>
        </div>
      </div>

      <h2 class="section-title">配件明细 · {{ detail.lines.length }} 项</h2>
      <div class="surface detail-lines">
        <div v-for="(line, index) in detail.lines" :key="line.item.id" class="detail-line">
          <div class="line-index">{{ index + 1 }}</div>
          <div class="line-main">
            <strong>{{ line.part?.name || "未知零件" }}</strong>
            <span>{{ line.part?.part_number || line.item.part_id }}</span>
            <small v-if="line.part?.spec">{{ line.part.spec }}</small>
          </div>
          <div class="line-value">
            <strong>¥{{ formatMoney(line.item.amount) }}</strong>
            <span>{{ formatQuantity(line.item.quantity) }} {{ line.part?.unit || "" }} × ¥{{ formatMoney(linePrice(line)) }}</span>
          </div>
        </div>
      </div>

      <div class="surface total-card">
        <span>单据合计</span>
        <strong>¥{{ formatMoney(detail.order.total_amount) }}</strong>
        <p v-if="detail.order.remark">备注：{{ detail.order.remark }}</p>
      </div>

      <div class="detail-actions">
        <van-button plain block icon="share-o" @click="shareOrder">分享单据</van-button>
        <van-button type="primary" block icon="printer" class="primary-action" @click="openPrintPreview">
          打印预览
        </van-button>
      </div>
      <p class="offline-note">详情和预览均读取本机数据，断网也可以使用。</p>
    </template>

    <div v-else-if="!loading" class="surface empty-state">
      <strong>没有找到这张单据</strong>
      <van-button plain size="small" @click="router.push('/records')">返回记录</van-button>
    </div>
  </section>
</template>

<style scoped>
.order-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 7px 3px 16px;
}
.order-heading span,
.order-heading strong { display: block; }
.order-heading span { color: var(--muted); font-size: 12px; }
.order-heading strong { margin-top: 5px; font-size: 20px; letter-spacing: .02em; }
.order-heading em {
  padding: 6px 9px;
  border-radius: 8px;
  color: #258351;
  background: #eaf8f0;
  font-size: 11px;
  font-style: normal;
  font-weight: 700;
}
.order-heading em.pending { color: #d86614; background: #fff3e8; }
.summary-card {
  display: grid;
  grid-template-columns: 1fr 1fr;
  padding: 4px 15px;
}
.summary-card div { min-width: 0; padding: 12px 0; border-bottom: 1px solid #edf1f5; }
.summary-card div:nth-last-child(-n + 2) { border-bottom: 0; }
.summary-card div:nth-child(odd):not(.wide) { padding-right: 12px; }
.summary-card .wide { grid-column: 1 / -1; }
.summary-card span,
.summary-card strong { display: block; }
.summary-card span { color: var(--muted); font-size: 11px; }
.summary-card strong { overflow: hidden; margin-top: 5px; font-size: 13px; text-overflow: ellipsis; }
.detail-lines { overflow: hidden; }
.detail-line {
  display: grid;
  grid-template-columns: 27px minmax(0, 1fr) auto;
  gap: 9px;
  padding: 14px;
  border-bottom: 1px solid #edf1f5;
}
.detail-line:last-child { border-bottom: 0; }
.line-index {
  width: 25px;
  height: 25px;
  display: grid;
  place-items: center;
  border-radius: 7px;
  color: #65758a;
  background: #f0f4f8;
  font-size: 11px;
}
.line-main strong,
.line-main span,
.line-main small,
.line-value strong,
.line-value span { display: block; }
.line-main strong { font-size: 14px; }
.line-main span { margin-top: 4px; color: var(--blue); font-size: 11px; }
.line-main small { margin-top: 3px; color: var(--muted); }
.line-value { text-align: right; }
.line-value strong { font-size: 14px; }
.line-value span { margin-top: 7px; color: var(--muted); font-size: 10px; }
.total-card {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  margin-top: 14px;
  padding: 16px;
}
.total-card span { color: var(--muted); }
.total-card strong { font-size: 22px; }
.total-card p { grid-column: 1 / -1; margin: 13px 0 0; padding-top: 12px; border-top: 1px solid #edf1f5; color: #64758a; font-size: 12px; }
.detail-actions { display: grid; grid-template-columns: .8fr 1.2fr; gap: 10px; margin-top: 18px; }
.detail-actions .van-button { height: 48px; border-radius: 10px; }
.offline-note { color: var(--muted); font-size: 11px; text-align: center; }
</style>
