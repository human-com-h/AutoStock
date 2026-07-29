<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ArrowLeft, Download, Printer } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { useRoute, useRouter } from "vue-router";
import { http } from "../api";
import { formatMoney, formatQuantity, moneyToChineseUpper } from "../utils/print";

const route = useRoute();
const router = useRouter();
const loading = ref(true);
const errorMessage = ref("");
const order = ref<any | null>(null);
const parts = ref<any[]>([]);
const partners = ref<any[]>([]);
const settings = ref<any>({});
const handwrittenLine = "________________";

const kind = computed(() => (route.params.kind === "purchases" ? "purchases" : "sales"));
const isPurchase = computed(() => kind.value === "purchases");
const partMap = computed(() => new Map(parts.value.map((part) => [part.id, part])));
const partner = computed(() => {
  if (!order.value) return null;
  const partnerId = isPurchase.value ? order.value.supplier_id : order.value.customer_id;
  return partners.value.find((row) => row.id === partnerId) || null;
});
const partnerName = computed(() => {
  if (partner.value?.name) return partner.value.name;
  if (!isPurchase.value && order.value?.customer_name) return order.value.customer_name;
  return "散客";
});
const partnerContact = computed(() =>
  isPurchase.value ? partner.value?.contact || "" : partnerName.value,
);
const partnerPhone = computed(() => partner.value?.phone || "");
const partnerAddress = computed(() =>
  isPurchase.value ? partner.value?.address || "" : partner.value?.location || "",
);
const documentTitle = computed(() => {
  const type = order.value?.order_type;
  if (type === "purchase_return") return "采购退货单";
  if (type === "sale_return") return "销售退货单";
  return isPurchase.value ? "采购入库单" : "销货清单";
});
const printableRows = computed(() =>
  (order.value?.items || []).map((item: any, index: number) => {
    const part = partMap.value.get(item.part_id) || {};
    const price = isPurchase.value ? item.purchase_price : item.sale_price;
    return {
      ...item,
      sequence: index + 1,
      part_number: part.part_number || item.part_id,
      name: part.name || "零件资料已停用",
      spec: part.spec || "—",
      unit: part.unit || settings.value.default_unit || "个",
      price,
    };
  }),
);
const pageSize = 18;
const pages = computed(() => {
  const rows = printableRows.value;
  const chunks: any[][] = [];
  for (let index = 0; index < rows.length; index += pageSize) {
    chunks.push(rows.slice(index, index + pageSize));
  }
  return chunks.length ? chunks : [[]];
});
const totalQuantity = computed(() =>
  printableRows.value.reduce(
    (total: number, row: any) => total + Number(row.quantity || 0),
    0,
  ),
);
const totalAmount = computed(() => Number(order.value?.total_amount || 0));
const isReversed = computed(() => Boolean(order.value?.reversed_by));
const statusText = computed(() => {
  if (isReversed.value) return "已红冲";
  if (order.value?.order_type?.endsWith("_return")) return "退货单";
  return "已过账";
});
const printExtraFields = computed(() => {
  const fields: Array<{ label: string; value: string }> = [];
  if (settings.value.print_payment_account) {
    fields.push({
      label: "收款账户",
      value: settings.value.print_payment_account,
    });
  }
  if (settings.value.print_wechat) {
    fields.push({ label: "联系微信", value: settings.value.print_wechat });
  }
  if (settings.value.print_warranty_period) {
    fields.push({ label: "售后期限", value: settings.value.print_warranty_period });
  }
  for (const field of settings.value.print_custom_fields || []) {
    if (!field.visible || !field.label) continue;
    fields.push({
      label: field.label,
      value: field.handwritten ? handwrittenLine : field.value || "—",
    });
  }
  return fields;
});

async function load() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const [orderData, partRows, partnerRows, printSettings] = await Promise.all([
      http.get(`/orders/${kind.value}/${String(route.params.id)}`),
      http.get("/parts"),
      http.get(isPurchase.value ? "/suppliers" : "/customers"),
      http.get("/settings"),
    ]);
    order.value = orderData;
    parts.value = partRows as unknown as any[];
    partners.value = partnerRows as unknown as any[];
    settings.value = printSettings;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "单据加载失败";
  } finally {
    loading.value = false;
  }
}

function printDocument() {
  const originalTitle = document.title;
  document.title = `${order.value?.order_no || "单据"}_${documentTitle.value}`;
  window.print();
  window.setTimeout(() => {
    document.title = originalTitle;
  }, 500);
}

function downloadPdf() {
  const anchor = document.createElement("a");
  anchor.href = `/api/orders/${kind.value}/${String(route.params.id)}/pdf`;
  anchor.download = `${order.value?.order_no || "单据"}.pdf`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  ElMessage.success("PDF 已开始下载");
}

onMounted(load);
</script>

<template>
  <div class="print-preview">
    <header class="preview-toolbar">
      <div class="toolbar-left">
        <el-button :icon="ArrowLeft" @click="router.back()">返回单据列表</el-button>
        <div>
          <strong>单据打印预览</strong>
          <span v-if="order">{{ order.order_no }} · A4 纵向 · 黑白</span>
        </div>
      </div>
      <div v-if="order" class="toolbar-actions">
        <el-tag :type="isReversed ? 'danger' : 'success'" effect="plain">{{ statusText }}</el-tag>
        <el-button :icon="Download" @click="downloadPdf">下载 PDF</el-button>
        <el-button type="primary" :icon="Printer" @click="printDocument">打印单据</el-button>
      </div>
    </header>

    <main class="preview-canvas">
      <div v-if="loading" class="preview-state">
        <el-skeleton :rows="10" animated />
      </div>
      <el-result
        v-else-if="errorMessage"
        icon="error"
        title="无法打开单据预览"
        :sub-title="errorMessage"
      >
        <template #extra><el-button @click="router.back()">返回</el-button></template>
      </el-result>

      <template v-else>
        <article v-for="(pageRows, pageIndex) in pages" :key="pageIndex" class="print-sheet">
          <div v-if="isReversed" class="void-watermark">已红冲</div>
          <header class="document-header">
            <div class="page-number">第 {{ pageIndex + 1 }} / {{ pages.length }} 页</div>
            <h1>{{ settings.shop_name || "AutoStock 汽配店" }}</h1>
            <h2>{{ documentTitle }}</h2>
          </header>

          <section class="document-meta">
            <div>
              <span>{{ isPurchase ? "入库仓库" : "发货仓库" }}</span>
              <strong>{{ settings.print_warehouse || "主仓库" }}</strong>
            </div>
            <div><span>录单日期</span><strong>{{ order.order_date }}</strong></div>
            <div><span>单据编号</span><strong>{{ order.order_no }}</strong></div>
            <div>
              <span>{{ isPurchase ? "供应商" : "客户名称" }}</span>
              <strong>{{ partnerName }}</strong>
            </div>
            <div><span>联系人</span><strong>{{ partnerContact || "—" }}</strong></div>
            <div><span>联系电话</span><strong>{{ partnerPhone || "—" }}</strong></div>
            <div class="meta-wide"><span>联系地址</span><strong>{{ partnerAddress || "—" }}</strong></div>
          </section>

          <table class="document-table">
            <colgroup>
              <col class="col-seq" />
              <col class="col-number" />
              <col class="col-name" />
              <col class="col-spec" />
              <col class="col-unit" />
              <col class="col-qty" />
              <col class="col-price" />
              <col class="col-amount" />
              <col class="col-remark" />
            </colgroup>
            <thead>
              <tr>
                <th>序号</th><th>商品编号</th><th>商品全名</th><th>规格</th><th>单位</th>
                <th>数量</th><th>单价</th><th>金额</th><th>备注</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in pageRows" :key="row.id">
                <td>{{ row.sequence }}</td>
                <td class="cell-left">{{ row.part_number }}</td>
                <td class="cell-left">{{ row.name }}</td>
                <td>{{ row.spec }}</td>
                <td>{{ row.unit }}</td>
                <td class="cell-number">{{ formatQuantity(row.quantity) }}</td>
                <td class="cell-number">{{ formatMoney(row.price) }}</td>
                <td class="cell-number">{{ formatMoney(row.amount) }}</td>
                <td class="cell-left">{{ row.remark || "" }}</td>
              </tr>
            </tbody>
          </table>

          <template v-if="pageIndex === pages.length - 1">
            <section class="document-total">
              <div class="total-label">合计</div>
              <div class="total-words">
                人民币（大写）：<strong>{{ moneyToChineseUpper(totalAmount) }}</strong>
              </div>
              <div class="total-quantity">{{ formatQuantity(totalQuantity) }}</div>
              <div class="total-amount">总金额 {{ formatMoney(totalAmount) }}</div>
            </section>

            <section class="document-footer">
              <div class="footer-line"><span>备注</span><strong>{{ order.remark || "—" }}</strong></div>
              <div v-if="settings.business_scope" class="footer-line">
                <span>经营项目</span><strong>{{ settings.business_scope }}</strong>
              </div>
              <div v-if="settings.print_notice" class="footer-line">
                <span>说明</span><strong>{{ settings.print_notice }}</strong>
              </div>
              <div class="shop-contact">
                <div><span>地址</span><strong>{{ settings.shop_address || "—" }}</strong></div>
                <div><span>电话</span><strong>{{ settings.shop_phone || "—" }}</strong></div>
              </div>
              <div v-if="printExtraFields.length" class="print-extra-grid">
                <div
                  v-for="field in printExtraFields"
                  :key="field.label"
                >
                  <span>{{ field.label }}</span><strong>{{ field.value }}</strong>
                </div>
              </div>
              <div class="signatures">
                <div><span>制单</span><strong>{{ settings.print_operator || "管理员" }}</strong></div>
                <div><span>复核</span><strong>{{ settings.print_reviewer || handwrittenLine }}</strong></div>
                <div><span>结算方式</span><strong>{{ settings.settlement_method || "现结" }}</strong></div>
                <div><span>{{ isPurchase ? "验收人" : "客户签字" }}</span><strong>{{ handwrittenLine }}</strong></div>
              </div>
            </section>
          </template>
          <div v-else class="continued">本页小计 {{ pageRows.length }} 项，接下页</div>
        </article>
      </template>
    </main>
  </div>
</template>

<style scoped>
.print-preview {
  min-height: 100vh;
  color: #111;
  background: #e8ebef;
}
.preview-toolbar {
  position: sticky;
  z-index: 20;
  top: 0;
  display: flex;
  min-height: 72px;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 12px 28px;
  border-bottom: 1px solid #d7dce2;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 3px 14px rgba(24, 34, 48, 0.06);
  backdrop-filter: blur(10px);
}
.toolbar-left,
.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.toolbar-left strong,
.toolbar-left span {
  display: block;
}
.toolbar-left strong {
  margin-bottom: 4px;
  font-size: 17px;
}
.toolbar-left span {
  color: #667085;
  font-size: 12px;
}
.preview-canvas {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 22px;
  padding: 30px 20px 48px;
}
.preview-state {
  width: min(760px, 90vw);
  padding: 32px;
  background: #fff;
}
.print-sheet {
  position: relative;
  width: 210mm;
  min-height: 297mm;
  padding: 10mm 11mm 9mm;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 7px 28px rgba(18, 28, 45, 0.16);
  font-family: SimSun, "Songti SC", "Microsoft YaHei", serif;
}
.void-watermark {
  position: absolute;
  z-index: 0;
  top: 128mm;
  left: 42mm;
  transform: rotate(-28deg);
  color: rgba(0, 0, 0, 0.08);
  font-size: 58px;
  font-weight: 800;
  letter-spacing: 18px;
  white-space: nowrap;
}
.document-header,
.document-meta,
.document-table,
.document-total,
.document-footer,
.continued {
  position: relative;
  z-index: 1;
}
.document-header {
  position: relative;
  margin-bottom: 4mm;
  text-align: center;
}
.document-header h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.12em;
}
.document-header h2 {
  margin: 2mm 0 0;
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 0.32em;
}
.page-number {
  position: absolute;
  top: 1mm;
  right: 0;
  font-size: 10px;
}
.document-meta {
  display: grid;
  grid-template-columns: 1fr 1fr 1.25fr;
  column-gap: 6mm;
  row-gap: 2.2mm;
  margin-bottom: 3mm;
  font-size: 10.5px;
}
.document-meta > div {
  display: flex;
  min-width: 0;
  gap: 2mm;
}
.document-meta span,
.document-footer span {
  flex: none;
  color: #333;
}
.document-meta strong,
.document-footer strong {
  min-width: 0;
  font-weight: 500;
  overflow-wrap: anywhere;
}
.document-meta .meta-wide {
  grid-column: 1 / -1;
}
.document-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 9px;
}
.document-table th,
.document-table td {
  height: 6.8mm;
  padding: 1mm 1.1mm;
  border: 0.35mm solid #111;
  text-align: center;
  vertical-align: middle;
  overflow-wrap: anywhere;
}
.document-table th {
  height: 8mm;
  font-size: 9.5px;
  font-weight: 700;
}
.document-table .cell-left {
  text-align: left;
}
.document-table .cell-number {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.col-seq { width: 5%; }
.col-number { width: 12%; }
.col-name { width: 22%; }
.col-spec { width: 12%; }
.col-unit { width: 7%; }
.col-qty { width: 9%; }
.col-price { width: 10%; }
.col-amount { width: 12%; }
.col-remark { width: 11%; }
.document-total {
  display: grid;
  grid-template-columns: 12mm 1fr 24mm 31mm;
  min-height: 10mm;
  border: 0.35mm solid #111;
  border-top: 0;
  font-size: 10px;
}
.document-total > div {
  display: flex;
  align-items: center;
  padding: 1.6mm 2mm;
  border-right: 0.35mm solid #111;
}
.document-total > div:last-child {
  border-right: 0;
}
.total-label,
.total-quantity {
  justify-content: center;
}
.total-amount {
  justify-content: flex-end;
  font-size: 11px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.document-footer {
  margin-top: 3mm;
  font-size: 9.5px;
  line-height: 1.45;
}
.footer-line {
  display: grid;
  grid-template-columns: 18mm 1fr;
  min-height: 7mm;
  align-items: start;
  padding: 1mm 1.5mm;
  border-bottom: 0.3mm solid #111;
}
.shop-contact {
  display: grid;
  grid-template-columns: 1.7fr 1fr;
  border-bottom: 0.3mm solid #111;
}
.shop-contact > div,
.print-extra-grid > div,
.signatures > div {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 2mm;
  padding: 1.5mm;
}
.shop-contact > div + div,
.signatures > div + div {
  border-left: 0.3mm solid #111;
}
.print-extra-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  border-bottom: 0.3mm solid #111;
}
.print-extra-grid > div {
  min-height: 7mm;
  border-top: 0;
}
.print-extra-grid > div:nth-child(even) {
  border-left: 0.3mm solid #111;
}
.signatures {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
}
.continued {
  margin-top: 3mm;
  text-align: right;
  font-size: 9px;
}

@media (max-width: 900px) {
  .preview-toolbar {
    position: static;
    align-items: flex-start;
    padding: 14px 16px;
  }
  .toolbar-left,
  .toolbar-actions {
    flex-wrap: wrap;
  }
  .preview-canvas {
    align-items: flex-start;
    overflow-x: auto;
  }
}

@media print {
  .print-preview,
  .preview-canvas {
    background: #fff;
  }
  .preview-toolbar {
    display: none !important;
  }
  .preview-canvas {
    display: block;
    padding: 0;
  }
  .print-sheet {
    width: 210mm;
    min-height: 297mm;
    margin: 0;
    box-shadow: none;
    break-after: page;
    page-break-after: always;
  }
  .print-sheet:last-child {
    break-after: auto;
    page-break-after: auto;
  }
}

@page {
  size: A4 portrait;
  margin: 0;
}
</style>
