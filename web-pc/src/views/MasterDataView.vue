<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { http } from "../api";

type Kind = "categories" | "brands" | "suppliers" | "customers";
const router = useRouter();
const kind = ref<Kind>("categories");
const rows = ref<any[]>([]);
const dialog = ref(false);
const editingId = ref("");
const form = reactive<any>({});
const configs: Record<Kind, { label: string; fields: [string, string][] }> = {
  categories: { label: "分类", fields: [["name", "分类名称"], ["sort_no", "排序"]] },
  brands: { label: "品牌", fields: [["name", "品牌名称"], ["remark", "备注"]] },
  suppliers: { label: "供应商", fields: [["name", "供应商名称"], ["contact", "联系人"], ["phone", "电话"], ["address", "地址"], ["remark", "备注"]] },
  customers: { label: "客户", fields: [["name", "客户名称"], ["phone", "电话"], ["remark", "备注"]] },
};
const config = computed(() => configs[kind.value]);
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
function openPurchases(row:any){router.push({path:"/purchase",query:{supplier_id:row.id}})}
watch(kind, load); onMounted(load);
</script>

<template>
  <div class="page-actions">
    <el-segmented v-model="kind" :options="Object.entries(configs).map(([value, item]) => ({ value, label: item.label }))" />
    <el-button type="primary" @click="open()">新增{{ config.label }}</el-button>
  </div>
  <div class="panel">
    <el-table :data="rows" stripe>
      <el-table-column prop="name" label="名称" min-width="180" />
      <el-table-column v-if="kind==='brands'" prop="part_count" label="零件引用数" />
      <el-table-column v-if="kind==='suppliers'" prop="contact" label="联系人" />
      <el-table-column v-if="kind==='suppliers'||kind==='customers'" prop="phone" label="电话" />
      <el-table-column v-if="kind==='suppliers'" prop="address" label="地址" />
      <el-table-column prop="remark" label="备注" />
      <el-table-column label="状态" width="90"><template #default="{row}">{{ row.is_active ? "启用" : "停用" }}</template></el-table-column>
      <el-table-column label="操作" width="230"><template #default="{row}">
        <el-button v-if="kind==='suppliers'" link type="primary" @click="openPurchases(row)">采购记录</el-button>
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
</template>
