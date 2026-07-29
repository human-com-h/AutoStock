<script setup lang="ts">
import { Calendar } from "@element-plus/icons-vue";
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { http } from "../api";
import { orderTypeLabel } from "../utils/order";

const route = useRoute();
const router = useRouter();
const parts = ref<any[]>([]);
const partners = ref<any[]>([]);
const orders = ref<any[]>([]);
const partnerId = ref("");
const customerName = ref("");
const lines = ref<any[]>([]);
const returnDialog = ref(false);
const submitting = ref(false);
const today = (() => {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
})();
const orderDate = ref(today);
const showHistoricalEntry = ref(false);
const returning = reactive<any>({ id:"", order_no:"", items:[] });
const purchase = computed(() => route.meta.kind === "purchase");
const title = computed(() => purchase.value ? "采购入库" : "销售出库");
const historicalMode = computed(() => orderDate.value < today);
function add() { lines.value.push({ part_id:"", quantity:1, price:0 }); }
function disableFutureDate(value: Date) {
  return value.getTime() > new Date(`${today}T23:59:59`).getTime();
}
function resetOrderDate() {
  orderDate.value = today;
  showHistoricalEntry.value = false;
}
function selectPart(line:any) {
  const part=parts.value.find(row=>row.id===line.part_id);
  line.price=part ? (purchase.value ? part.purchase_price : part.sale_price) : 0;
}
async function load() {
  const [partRows, partnerRows, orderRows] = await Promise.all([
    http.get("/parts"),
    http.get(purchase.value ? "/suppliers" : "/customers"),
    http.get(purchase.value ? "/orders/purchases" : "/orders/sales"),
  ]);
  parts.value=partRows as unknown as any[]; partners.value=partnerRows as unknown as any[];
  const supplierFilter=purchase.value?String(route.query.supplier_id||""):"";
  const orderList=orderRows as unknown as any[];
  orders.value=supplierFilter?orderList.filter(row=>row.supplier_id===supplierFilter):orderList;
  partnerId.value=supplierFilter; customerName.value=""; lines.value=[]; add();
  resetOrderDate();
}
async function createCustomer() {
  const { value }=await ElMessageBox.prompt("输入客户名称", "开单时新增客户", { inputValidator:value=>!!value||"请输入名称" });
  const row:any=await http.post("/customers",{name:value}); partners.value.push(row); partnerId.value=row.id;
}
async function submit() {
  const items=lines.value.filter(row=>row.part_id).map(row=>({
    part_id:row.part_id, quantity:row.quantity,
    [purchase.value?"purchase_price":"sale_price"]:row.price,
  }));
  if (!items.length) {
    ElMessage.warning("请至少选择一个零件");
    return;
  }
  if (items.some(item=>!Number.isFinite(item.quantity)||item.quantity<=0)) {
    ElMessage.warning("零件数量必须大于 0");
    return;
  }
  const priceKey=purchase.value?"purchase_price":"sale_price";
  if (items.some(item=>!Number.isInteger(item[priceKey])||item[priceKey]<0)) {
    ElMessage.warning(`${purchase.value?"进价":"售价"}必须是大于等于 0 的整数分`);
    return;
  }
  if (new Set(items.map(item=>item.part_id)).size!==items.length) {
    ElMessage.warning("同一个零件不能重复添加，请合并数量");
    return;
  }
  const payload:any={items,order_date:orderDate.value};
  if(purchase.value) payload.supplier_id=partnerId.value||undefined;
  else {payload.customer_id=partnerId.value||undefined;payload.customer_name=customerName.value||undefined;}
  submitting.value=true;
  try {
    await http.post(purchase.value?"/orders/purchases":"/orders/sales",payload);
    ElMessage.success(
      `${historicalMode.value ? `${title.value}历史补录` : title.value}单已保存并过账`,
    );
    await load();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : `${title.value}单保存失败`);
  } finally {
    submitting.value=false;
  }
}
async function voidOrder(row:any) {
  await ElMessageBox.confirm(`确定撤销/红冲单据 ${row.order_no}？`,"确认操作",{type:"warning"});
  await http.post(`/orders/${purchase.value?"purchases":"sales"}/${row.id}/void`);
  ElMessage.success("单据已处理"); await load();
}
function openReturn(row:any) {
  Object.assign(returning,{id:row.id,order_no:row.order_no,items:row.items.map((item:any)=>({...item,return_quantity:0}))});
  returnDialog.value=true;
}
async function submitReturn() {
  const items=returning.items.filter((item:any)=>item.return_quantity>0).map((item:any)=>({part_id:item.part_id,quantity:item.return_quantity}));
  await http.post(`/orders/${purchase.value?"purchases":"sales"}/${returning.id}/returns`,{items});
  returnDialog.value=false;ElMessage.success("退货单已生成");await load();
}
function exportOrders(){window.open(`/api/excel/export/orders/${purchase.value?"purchases":"sales"}`)}
function previewOrder(row:any) {
  router.push(`/orders/${purchase.value?"purchases":"sales"}/${row.id}/print`);
}
watch(()=>route.meta.kind,load); onMounted(load);
</script>
<template>
  <div class="panel order-form">
    <div class="page-actions">
      <div>
        <h3>新建{{title}}单</h3>
        <span class="form-subtitle">默认业务日期为今天，需要补录时可选择之前的日期</span>
      </div>
      <div class="form-actions">
        <el-button :icon="Calendar" @click="showHistoricalEntry=!showHistoricalEntry">
          {{ historicalMode ? `历史日期 · ${orderDate}` : "补录历史单据" }}
        </el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存并过账</el-button>
      </div>
    </div>
    <div v-if="showHistoricalEntry" class="historical-entry">
      <div>
        <strong>业务日期</strong>
        <span>只能选择今天或之前的日期；单据和报表按业务日期统计。</span>
      </div>
      <el-date-picker
        v-model="orderDate"
        type="date"
        value-format="YYYY-MM-DD"
        format="YYYY-MM-DD"
        :clearable="false"
        :disabled-date="disableFutureDate"
        placeholder="选择业务日期"
      />
      <el-button v-if="historicalMode" link type="primary" @click="resetOrderDate">恢复今天</el-button>
    </div>
    <el-alert
      v-if="historicalMode"
      class="historical-alert"
      type="warning"
      :closable="false"
      show-icon
      :title="`正在补录 ${orderDate} 的${title}业务；库存流水按当前实际录入时刻过账。`"
    />
    <div class="partner-row">
      <el-select v-model="partnerId" filterable clearable :placeholder="purchase?'选择供应商（可选）':'选择客户（可选）'" style="width:300px">
        <el-option v-for="row in partners" :key="row.id" :label="row.name" :value="row.id"/>
      </el-select>
      <el-button v-if="!purchase" @click="createCustomer">即时新建客户</el-button>
      <el-input v-if="!purchase&&!partnerId" v-model="customerName" placeholder="或直接输入散客名称" style="width:260px"/>
    </div>
    <el-table :data="lines">
      <el-table-column label="零件" min-width="260"><template #default="{row}"><el-select v-model="row.part_id" filterable style="width:100%" @change="selectPart(row)"><el-option v-for="part in parts" :key="part.id" :label="`${part.part_number} · ${part.name}`" :value="part.id" :disabled="!part.is_active"/></el-select></template></el-table-column>
      <el-table-column label="数量"><template #default="{row}"><el-input-number v-model="row.quantity" :min=".001" :precision="3"/></template></el-table-column>
      <el-table-column :label="purchase?'进价(分)':'售价(分)'"><template #default="{row}"><el-input-number v-model="row.price" :min="0"/></template></el-table-column>
      <el-table-column label="金额"><template #default="{row}">¥ {{(row.quantity*row.price/100).toFixed(2)}}</template></el-table-column>
      <el-table-column width="70"><template #default="scope"><el-button link type="danger" @click="lines.splice(scope.$index,1)">移除</el-button></template></el-table-column>
    </el-table><el-button style="margin-top:12px" @click="add">添加一行</el-button>
  </div>
  <div class="panel" style="margin-top:18px"><div class="page-actions"><h3>最近{{title}}单</h3><el-button @click="exportOrders">导出明细</el-button></div><el-table :data="orders">
    <el-table-column prop="order_no" label="单号"/><el-table-column prop="order_date" label="日期"/><el-table-column label="业务类型"><template #default="{row}">{{ orderTypeLabel(row.order_type) }}</template></el-table-column>
    <el-table-column label="金额"><template #default="{row}">¥ {{(row.total_amount/100).toFixed(2)}}</template></el-table-column>
    <el-table-column label="操作" width="215"><template #default="{row}"><el-button link type="primary" @click="previewOrder(row)">预览</el-button><el-button v-if="!row.source_order_id&&!row.reversed_by" link type="primary" @click="openReturn(row)">退货</el-button><el-button v-if="!row.reversed_by" link type="danger" @click="voidOrder(row)">撤销/红冲</el-button></template></el-table-column>
  </el-table></div>
  <el-dialog v-model="returnDialog" :title="`退货 · ${returning.order_no}`" width="620">
    <el-table :data="returning.items"><el-table-column prop="part_id" label="零件ID"/><el-table-column prop="quantity" label="原数量"/><el-table-column label="退货数量"><template #default="{row}"><el-input-number v-model="row.return_quantity" :min="0" :max="row.quantity" :precision="3"/></template></el-table-column></el-table>
    <template #footer><el-button @click="returnDialog=false">取消</el-button><el-button type="primary" @click="submitReturn">生成退货单</el-button></template>
  </el-dialog>
</template>
<style scoped>
.partner-row{display:flex;gap:10px;margin-bottom:16px}
.order-form h3{margin:0}
.form-subtitle{display:block;margin-top:5px;color:#8490a2;font-size:12px}
.form-actions{display:flex;gap:8px}
.historical-entry{display:flex;align-items:center;gap:14px;margin:0 0 14px;padding:14px 16px;background:#f6f8fc;border:1px solid #e2e7ef;border-radius:8px}
.historical-entry>div:first-child{flex:1}
.historical-entry strong,.historical-entry span{display:block}
.historical-entry strong{margin-bottom:4px;color:#273248;font-size:13px}
.historical-entry span{color:#7d899a;font-size:12px}
.historical-alert{margin-bottom:14px}
@media(max-width:900px){
  .page-actions{align-items:flex-start;flex-direction:column}
  .form-actions{width:100%;flex-wrap:wrap}
  .historical-entry{align-items:flex-start;flex-direction:column}
}
</style>
