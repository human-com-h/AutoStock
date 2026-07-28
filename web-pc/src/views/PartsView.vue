<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { http } from "../api";

const rows = ref<any[]>([]);
const keyword = ref("");
const dialog = ref(false);
const editingId = ref("");
const upload = ref<HTMLInputElement>();
const form = reactive<any>({
  part_number: "", name: "", oe_number: "", unit: "个",
  purchase_price: 0, sale_price: 0, min_stock: 0, max_stock: null, location: "",
});
function download(url:string) { window.open(url); }
async function load() { rows.value = await http.get("/parts", { params: { keyword: keyword.value || undefined } }) as unknown as any[]; }
function open(row?:any) {
  Object.assign(form, row || { part_number:"", name:"", oe_number:"", unit:"个", purchase_price:0, sale_price:0, min_stock:0, max_stock:null, location:"" });
  editingId.value = row?.id || ""; dialog.value = true;
}
async function save() {
  if (editingId.value) await http.put(`/parts/${editingId.value}`, form);
  else await http.post("/parts", form);
  dialog.value=false; ElMessage.success("零件已保存"); await load();
}
async function remove(row:any) { await http.delete(`/parts/${row.id}`); ElMessage.success(row.is_active ? "零件已删除或停用" : "操作完成"); await load(); }
async function importFile(event:Event) {
  const file=(event.target as HTMLInputElement).files?.[0]; if(!file)return;
  const data=new FormData(); data.append("file",file);
  const result:any=await http.post("/excel/import/parts",data);
  ElMessage.success(`导入 ${result.imported} 行，错误 ${result.errors.length} 行`);
  if(result.errors.length) ElMessage.warning(result.errors.slice(0,3).map((x:any)=>`第${x.row}行：${x.message}`).join("；"));
  await load(); (event.target as HTMLInputElement).value="";
}
onMounted(load);
</script>
<template>
  <div class="page-actions">
    <div><el-input v-model="keyword" clearable placeholder="编号 / OE号 / 名称 / 拼音" style="width:320px" @keyup.enter="load"/><el-button @click="load">查询</el-button></div>
    <div>
      <el-button @click="download('/api/excel/template/parts')">下载模板</el-button>
      <el-button @click="upload?.click()">Excel 导入</el-button>
      <el-button @click="download('/api/excel/export/parts')">导出</el-button>
      <el-button type="primary" @click="open()">新增零件</el-button>
      <input ref="upload" hidden type="file" accept=".xlsx" @change="importFile"/>
    </div>
  </div>
  <div class="panel"><el-table :data="rows" stripe>
    <el-table-column prop="part_number" label="编号"/><el-table-column prop="oe_number" label="OE号"/><el-table-column prop="name" label="名称"/>
    <el-table-column prop="unit" label="单位" width="70"/><el-table-column prop="location" label="货位"/>
    <el-table-column label="进价"><template #default="{row}">¥{{(row.purchase_price/100).toFixed(2)}}</template></el-table-column>
    <el-table-column label="售价"><template #default="{row}">¥{{(row.sale_price/100).toFixed(2)}}</template></el-table-column>
    <el-table-column label="状态" width="70"><template #default="{row}">{{row.is_active?"启用":"停用"}}</template></el-table-column>
    <el-table-column label="操作" width="130"><template #default="{row}"><el-button link type="primary" @click="open(row)">编辑</el-button><el-button link type="danger" @click="remove(row)">删除</el-button></template></el-table-column>
  </el-table></div>
  <el-dialog v-model="dialog" :title="editingId?'编辑零件':'新增零件'" width="620">
    <el-form :model="form" label-width="105px" class="part-form">
      <el-form-item label="零件编号"><el-input v-model="form.part_number"/></el-form-item><el-form-item label="零件名称"><el-input v-model="form.name"/></el-form-item>
      <el-form-item label="OE号"><el-input v-model="form.oe_number"/></el-form-item><el-form-item label="单位"><el-input v-model="form.unit"/></el-form-item>
      <el-form-item label="货位"><el-input v-model="form.location"/></el-form-item><el-form-item label="参考进价(分)"><el-input-number v-model="form.purchase_price" :min="0"/></el-form-item>
      <el-form-item label="参考售价(分)"><el-input-number v-model="form.sale_price" :min="0"/></el-form-item><el-form-item label="最低库存"><el-input-number v-model="form.min_stock" :min="0"/></el-form-item>
      <el-form-item label="最高库存"><el-input-number v-model="form.max_stock" :min="0"/></el-form-item>
    </el-form>
    <template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
  </el-dialog>
</template>
<style scoped>.part-form{display:grid;grid-template-columns:1fr 1fr;gap:0 12px}.part-form .el-form-item:nth-child(3){grid-column:1/-1}</style>
