<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { http } from "../api";
import {
  orderAmountSign,
  orderDirectionLabel,
  orderTypeLabel,
} from "../utils/order";

type Kind = "categories" | "brands" | "suppliers" | "customers";
const kind = ref<Kind>("categories");
const rows = ref<any[]>([]);
const dialog = ref(false);
const editingId = ref("");
const form = reactive<any>({});
const locationFilter = ref("");
const recordDialog = ref(false);
const recordLoading = ref(false);
const businessRecords = ref<any[]>([]);
const partNames = ref<Record<string, string>>({});
const recordContext = reactive({
  kind: "suppliers" as "suppliers" | "customers",
  name: "",
});
const configs: Record<Kind, { label: string; fields: [string, string][] }> = {
  categories: { label: "分类", fields: [["name", "分类名称"], ["sort_no", "排序"]] },
  brands: { label: "品牌", fields: [["name", "品牌名称"], ["remark", "备注"]] },
  suppliers: { label: "供应商", fields: [["name", "供应商名称"], ["contact", "联系人"], ["phone", "电话"], ["address", "地址"], ["remark", "备注"]] },
  customers: { label: "客户", fields: [["name", "客户名称"], ["phone", "电话"], ["location", "位置"], ["remark", "备注"]] },
};
const config = computed(() => configs[kind.value]);
const customerLocations = computed(() =>
  Array.from(
    new Set(
      rows.value
        .map(row => String(row.location || "").trim())
        .filter(Boolean),
    ),
  ).sort((a, b) => a.localeCompare(b, "zh-CN")),
);
const filteredRows = computed(() =>
  kind.value === "customers" && locationFilter.value
    ? rows.value.filter(row => row.location === locationFilter.value)
    : rows.value,
);
const recordTitle = computed(
  () => `${recordContext.name} · ${recordContext.kind === "suppliers" ? "进货记录" : "出货记录"}`,
);
const recordNetAmount = computed(() =>
  businessRecords.value.reduce(
    (total, row) => total + orderAmountSign(row.order_type) * row.total_amount,
    0,
  ),
);
const inboundCount = computed(
  () => businessRecords.value.filter(row => orderDirectionLabel(row.order_type) === "入库").length,
);
const outboundCount = computed(
  () => businessRecords.value.filter(row => orderDirectionLabel(row.order_type) === "出库").length,
);
async function load() { rows.value = await http.get(`/${kind.value}`) as unknown as any[]; }
function open(row?: any) {
  Object.keys(form).forEach(key => delete form[key]);
  Object.assign(form, row || { sort_no: 0 });
  editingId.value = row?.id || "";
  dialog.value = true;
}
async function save() {
  const payload = Object.fromEntries(config.value.fields.map(([key]) => [key, form[key]]));
  if (editingId.value) await http.put(`/${kind.value}/${editingId.value}`, payload);
  else await http.post(`/${kind.value}`, payload);
  dialog.value = false; ElMessage.success("已保存"); await load();
}
async function toggle(row: any) {
  await http.put(`/${kind.value}/${row.id}`, { is_active: row.is_active ? 0 : 1 });
  await load();
}
async function openRecords(row: any) {
  recordContext.kind = kind.value === "suppliers" ? "suppliers" : "customers";
  recordContext.name = row.name;
  businessRecords.value = [];
  partNames.value = {};
  recordDialog.value = true;
  recordLoading.value = true;
  try {
    const purchase = recordContext.kind === "suppliers";
    const [orderRows, partRows] = await Promise.all([
      http.get(purchase ? "/orders/purchases" : "/orders/sales", {
        params: {
          limit: 500,
          [purchase ? "supplier_id" : "customer_id"]: row.id,
        },
      }),
      http.get("/parts"),
    ]);
    businessRecords.value = orderRows as unknown as any[];
    partNames.value = Object.fromEntries(
      (partRows as unknown as any[]).map(part => [part.id, `${part.part_number} · ${part.name}`]),
    );
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "业务记录加载失败");
  } finally {
    recordLoading.value = false;
  }
}
function itemSummary(row: any) {
  return row.items
    .map((item: any) => `${partNames.value[item.part_id] || "未知零件"} × ${item.quantity}`)
    .join("；");
}
function money(value: number) {
  return `¥ ${(value / 100).toLocaleString("zh-CN", { minimumFractionDigits: 2 })}`;
}
watch(kind, () => {
  locationFilter.value = "";
  void load();
});
onMounted(load);
</script>

<template>
  <div class="page-actions">
    <div class="master-filters">
      <el-segmented v-model="kind" :options="Object.entries(configs).map(([value, item]) => ({ value, label: item.label }))" />
      <el-select
        v-if="kind==='customers'"
        v-model="locationFilter"
        clearable
        placeholder="按位置筛选客户"
        style="width:220px"
      >
        <el-option v-for="location in customerLocations" :key="location" :label="location" :value="location" />
      </el-select>
    </div>
    <el-button type="primary" @click="open()">新增{{ config.label }}</el-button>
  </div>
  <div class="panel">
    <el-table :data="filteredRows" stripe>
      <el-table-column prop="name" label="名称" min-width="180" />
      <el-table-column v-if="kind==='brands'" prop="part_count" label="零件引用数" />
      <el-table-column v-if="kind==='suppliers'" prop="contact" label="联系人" />
      <el-table-column v-if="kind==='suppliers'||kind==='customers'" prop="phone" label="电话" />
      <el-table-column v-if="kind==='suppliers'" prop="address" label="地址" />
      <el-table-column v-if="kind==='customers'" prop="location" label="位置" />
      <el-table-column prop="remark" label="备注" />
      <el-table-column label="状态" width="90"><template #default="{row}">{{ row.is_active ? "启用" : "停用" }}</template></el-table-column>
      <el-table-column label="操作" width="250"><template #default="{row}">
        <el-button v-if="kind==='suppliers'||kind==='customers'" link type="primary" @click="openRecords(row)">业务记录</el-button>
        <el-button link type="primary" @click="open(row)">编辑</el-button>
        <el-button link @click="toggle(row)">{{ row.is_active ? "停用" : "启用" }}</el-button>
      </template></el-table-column>
    </el-table>
  </div>
  <el-dialog v-model="dialog" :title="`${editingId?'编辑':'新增'}${config.label}`" width="520">
    <el-form :model="form" label-width="100">
      <el-form-item v-for="[field,label] in config.fields" :key="field" :label="label">
        <el-input-number v-if="field==='sort_no'" v-model="form[field]" />
        <el-input v-else v-model="form[field]" />
      </el-form-item>
    </el-form>
    <template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
  </el-dialog>
  <el-dialog v-model="recordDialog" :title="recordTitle" width="980">
    <div class="record-summary">
      <span>共 <strong>{{ businessRecords.length }}</strong> 张单据</span>
      <span>入库 <strong>{{ inboundCount }}</strong> 张</span>
      <span>出库 <strong>{{ outboundCount }}</strong> 张</span>
      <span>往来净额 <strong>{{ money(recordNetAmount) }}</strong></span>
    </div>
    <el-table :data="businessRecords" v-loading="recordLoading" stripe max-height="520">
      <el-table-column prop="order_date" label="日期" width="115" />
      <el-table-column prop="order_no" label="单号" width="165" />
      <el-table-column label="业务类型" width="120">
        <template #default="{row}">{{ orderTypeLabel(row.order_type) }}</template>
      </el-table-column>
      <el-table-column label="方向" width="90">
        <template #default="{row}">
          <el-tag :type="orderDirectionLabel(row.order_type)==='入库'?'success':'warning'">
            {{ orderDirectionLabel(row.order_type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="零件明细" min-width="300">
        <template #default="{row}">{{ itemSummary(row) }}</template>
      </el-table-column>
      <el-table-column label="金额" width="130" align="right">
        <template #default="{row}">{{ money(orderAmountSign(row.order_type)*row.total_amount) }}</template>
      </el-table-column>
    </el-table>
  </el-dialog>
</template>

<style scoped>
.master-filters {
  display: flex;
  align-items: center;
  gap: 12px;
}
.record-summary {
  display: flex;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.record-summary span {
  padding: 8px 12px;
  background: #f4f7fb;
  border-radius: 6px;
  color: #657186;
  font-size: 13px;
}
.record-summary strong {
  color: #172033;
}
</style>
