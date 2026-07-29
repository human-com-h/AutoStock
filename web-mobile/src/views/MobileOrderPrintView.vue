<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  getPrintSettings,
  type MobilePrintSettings,
} from "../db/schema";
import {
  getLocalOrderDetail,
  type LocalOrderDetail,
  type OrderKind,
} from "../services/orders";
import { formatMoney, formatQuantity, moneyToChineseUpper } from "../utils/print";

const route = useRoute();
const router = useRouter();
const detail = ref<LocalOrderDetail | null>(null);
const settings = ref<MobilePrintSettings | null>(null);
const loading = ref(true);
const previousTitle = document.title;
const kind = computed<OrderKind>(() =>
  route.params.kind === "purchase" ? "purchase" : "sale",
);
const isPurchase = computed(() => kind.value === "purchase");
const documentTitle = computed(() =>
  isPurchase.value ? "采购入库清单" : "销货清单",
);
const partnerName = computed(() => {
  if (!detail.value) return "未填写";
  if (!isPurchase.value && "customer_name" in detail.value.order) {
    return detail.value.order.customer_name || detail.value.partner?.name || "散客";
  }
  return detail.value.partner?.name || "未填写";
});
const visibleCustomFields = computed(
  () => settings.value?.print_custom_fields.filter((field) => field.visible) || [],
);

function partnerField(key: string): string {
  const value = detail.value?.partner?.[key];
  return typeof value === "string" ? value : "";
}

function linePrice(line: LocalOrderDetail["lines"][number]): number {
  return "purchase_price" in line.item ? line.item.purchase_price : line.item.sale_price;
}

function printDocument(): void {
  document.title = `${detail.value?.order.order_no || "单据"}-${documentTitle.value}`;
  window.print();
}

onMounted(async () => {
  [detail.value, settings.value] = await Promise.all([
    getLocalOrderDetail(kind.value, String(route.params.id)),
    getPrintSettings(),
  ]);
  loading.value = false;
});

onUnmounted(() => {
  document.title = previousTitle;
});
</script>

<template>
  <div class="mobile-print-view">
    <div class="preview-toolbar no-print">
      <button type="button" @click="router.back()"><van-icon name="arrow-left" /> 返回</button>
      <div><strong>打印预览</strong><span>内容只读，请核对后再打印</span></div>
      <button class="print-button" type="button" :disabled="!detail" @click="printDocument">
        <van-icon name="printer" /> 打印 / PDF
      </button>
    </div>

    <main v-if="detail && settings" class="paper-shell">
      <article class="print-document">
        <header class="document-header">
          <div class="page-number">第 1 / 1 页</div>
          <h1>{{ settings.shop_name }}</h1>
          <h2>{{ documentTitle }}</h2>
        </header>

        <section class="document-meta">
          <div><b>单据编号：</b>{{ detail.order.order_no }}</div>
          <div><b>单据日期：</b>{{ detail.order.order_date }}</div>
          <div><b>{{ isPurchase ? "供应商" : "客户名称" }}：</b>{{ partnerName }}</div>
          <div><b>联系电话：</b>{{ partnerField("phone") || "—" }}</div>
          <div class="wide">
            <b>联系地址：</b>{{ partnerField("address") || partnerField("location") || "—" }}
          </div>
        </section>

        <table class="document-table">
          <thead>
            <tr>
              <th class="sequence">序号</th>
              <th>商品全名 / 编号</th>
              <th class="spec">规格</th>
              <th class="unit">单位</th>
              <th class="number">数量</th>
              <th class="money">单价</th>
              <th class="money amount">金额</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(line, index) in detail.lines" :key="line.item.id">
              <td class="center">{{ index + 1 }}</td>
              <td>
                <strong>{{ line.part?.name || "未知零件" }}</strong>
                <small>{{ line.part?.part_number || line.item.part_id }}</small>
              </td>
              <td class="center">{{ line.part?.spec || "—" }}</td>
              <td class="center">{{ line.part?.unit || "—" }}</td>
              <td class="right">{{ formatQuantity(line.item.quantity) }}</td>
              <td class="right">{{ formatMoney(linePrice(line)) }}</td>
              <td class="right">{{ formatMoney(line.item.amount) }}</td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <th colspan="4" class="total-label">合计</th>
              <th class="right">
                {{ formatQuantity(detail.lines.reduce((sum, line) => sum + Number(line.item.quantity), 0)) }}
              </th>
              <th></th>
              <th class="right">{{ formatMoney(detail.order.total_amount) }}</th>
            </tr>
          </tfoot>
        </table>

        <section class="amount-uppercase">
          <b>人民币（大写）：</b>
          <span>{{ moneyToChineseUpper(detail.order.total_amount) }}</span>
          <b>小写：</b>
          <span>¥ {{ formatMoney(detail.order.total_amount) }}</span>
        </section>

        <section class="document-notes">
          <div><b>摘　要：</b>{{ detail.order.remark || "—" }}</div>
          <div v-if="settings.business_scope"><b>经营项目：</b>{{ settings.business_scope }}</div>
          <div v-if="settings.print_notice"><b>说　明：</b>{{ settings.print_notice }}</div>
          <div class="contacts">
            <span><b>地址：</b>{{ settings.shop_address || "—" }}</span>
            <span><b>电话：</b>{{ settings.shop_phone || "—" }}</span>
          </div>
          <div v-if="settings.print_payment_account || settings.print_wechat" class="contacts">
            <span v-if="settings.print_payment_account"><b>收款账户：</b>{{ settings.print_payment_account }}</span>
            <span v-if="settings.print_wechat"><b>微信：</b>{{ settings.print_wechat }}</span>
          </div>
        </section>

        <section class="signature-grid">
          <div><b>制单人：</b>{{ settings.print_operator || "—" }}</div>
          <div><b>结算方式：</b>{{ settings.settlement_method || "—" }}</div>
          <div><b>仓库：</b>{{ settings.print_warehouse || "—" }}</div>
          <div><b>复核人：</b>{{ settings.print_reviewer || "____________" }}</div>
          <div v-for="field in visibleCustomFields" :key="field.label">
            <b>{{ field.label }}：</b>
            <span v-if="field.handwritten" class="handwrite-line">{{ field.value }}</span>
            <span v-else>{{ field.value || "—" }}</span>
          </div>
          <div><b>客户签字：</b><span class="handwrite-line"></span></div>
        </section>
      </article>
    </main>

    <div v-else-if="!loading" class="preview-error">
      <strong>无法生成预览</strong>
      <span>本机中没有找到这张单据。</span>
      <button type="button" @click="router.push('/records')">返回单据记录</button>
    </div>
  </div>
</template>

<style scoped>
.mobile-print-view {
  min-height: 100vh;
  color: #111;
  background: #e6e8eb;
}
.preview-toolbar {
  position: sticky;
  z-index: 20;
  top: 0;
  min-height: 62px;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 8px;
  padding: max(8px, env(safe-area-inset-top)) 10px 8px;
  color: white;
  background: #142236;
  box-shadow: 0 2px 14px rgb(0 0 0 / 20%);
}
.preview-toolbar button {
  min-height: 38px;
  padding: 0 10px;
  border: 1px solid rgb(255 255 255 / 30%);
  border-radius: 8px;
  color: white;
  background: transparent;
  font-size: 12px;
}
.preview-toolbar .print-button {
  border-color: white;
  color: #111;
  background: white;
  font-weight: 700;
}
.preview-toolbar div { min-width: 0; text-align: center; }
.preview-toolbar strong,
.preview-toolbar span { display: block; }
.preview-toolbar strong { font-size: 14px; }
.preview-toolbar span { margin-top: 2px; opacity: .72; font-size: 9px; }
.paper-shell { padding: 12px 8px 32px; }
.print-document {
  width: min(100%, 794px);
  min-height: 1123px;
  margin: 0 auto;
  padding: 28px 24px 32px;
  color: #000;
  background: #fff;
  box-shadow: 0 8px 28px rgb(0 0 0 / 14%);
  font-family: "SimSun", "Songti SC", serif;
  font-size: 11px;
}
.document-header { position: relative; padding: 0 64px 14px; text-align: center; }
.document-header h1 { margin: 0; font-size: clamp(18px, 5vw, 28px); line-height: 1.2; }
.document-header h2 { margin: 6px 0 0; font-size: clamp(15px, 4vw, 21px); letter-spacing: .15em; }
.page-number { position: absolute; top: 1px; right: 0; font-size: 10px; }
.document-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 15px;
  padding: 9px 4px;
  border-top: 2px solid #000;
}
.document-meta .wide { grid-column: 1 / -1; }
.document-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.document-table th,
.document-table td { height: 29px; padding: 4px; border: 1px solid #000; vertical-align: middle; }
.document-table th { font-weight: 700; text-align: center; }
.document-table strong,
.document-table small { display: block; }
.document-table small { margin-top: 2px; font-family: Arial, sans-serif; font-size: 8px; }
.document-table .sequence { width: 7%; }
.document-table .spec { width: 13%; }
.document-table .unit { width: 8%; }
.document-table .number { width: 10%; }
.document-table .money { width: 12%; }
.document-table .amount { width: 14%; }
.center { text-align: center; }
.right { text-align: right; font-variant-numeric: tabular-nums; }
.total-label { letter-spacing: .7em; }
.amount-uppercase {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto;
  gap: 8px;
  padding: 9px 6px;
  border: 1px solid #000;
  border-top: 0;
}
.document-notes { border-bottom: 1px solid #000; }
.document-notes > div { padding: 6px 4px; border-bottom: 1px solid #777; line-height: 1.45; }
.document-notes > div:last-child { border-bottom: 0; }
.contacts { display: flex; justify-content: space-between; gap: 18px; }
.signature-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 9px 16px;
  padding: 12px 4px 0;
}
.signature-grid div { min-width: 0; }
.handwrite-line {
  display: inline-block;
  min-width: 58px;
  min-height: 14px;
  border-bottom: 1px solid #000;
}
.preview-error {
  min-height: 70vh;
  display: grid;
  place-content: center;
  gap: 8px;
  padding: 20px;
  text-align: center;
}
.preview-error strong { font-size: 18px; }
.preview-error button { margin-top: 8px; padding: 10px 15px; }

@media (max-width: 430px) {
  .print-document { min-height: calc(100vh - 100px); padding: 20px 10px 26px; font-size: 9px; }
  .document-header { padding-inline: 48px; }
  .document-meta { gap: 5px 8px; }
  .document-table th,
  .document-table td { padding: 3px 2px; }
  .amount-uppercase { grid-template-columns: auto 1fr; }
  .signature-grid { grid-template-columns: 1fr 1fr; gap: 8px; }
}

@media print {
  @page { size: A4 portrait; margin: 9mm; }
  .mobile-print-view,
  .paper-shell { min-height: auto; padding: 0; background: #fff; }
  .no-print { display: none !important; }
  .print-document {
    width: auto;
    min-height: auto;
    margin: 0;
    padding: 0;
    box-shadow: none;
    font-size: 10pt;
  }
  .document-header h1 { font-size: 20pt; }
  .document-header h2 { font-size: 15pt; }
  .document-table thead { display: table-header-group; }
  .document-table tr,
  .amount-uppercase,
  .document-notes,
  .signature-grid { break-inside: avoid; }
}
</style>
