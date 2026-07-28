<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { http } from "../api";

const form = reactive({ shop_name: "", default_unit: "个", allow_negative_stock: true, stale_days: 180 });
const backups = ref<any[]>([]);
const password = reactive({ current_password: "", new_password: "" });
async function load() {
  Object.assign(form, await http.get("/settings"));
  backups.value = await http.get("/backups") as unknown as any[];
}
async function save() { Object.assign(form, await http.put("/settings", form)); ElMessage.success("系统设置已保存"); }
async function changePassword() { await http.put("/settings/password", password); password.current_password=""; password.new_password=""; ElMessage.success("密码已修改"); }
async function backup() { await http.post("/backups"); await load(); ElMessage.success("备份已创建"); }
async function restore(row:any) {
  await ElMessageBox.confirm(`确定恢复到 ${row.name}？当前数据会先自动备份。`, "恢复备份", { type:"warning" });
  await http.post("/backups/restore", { name: row.name, confirm: "RESTORE" }); ElMessage.success("恢复完成，请刷新页面");
}
onMounted(load);
</script>
<template>
  <el-tabs>
    <el-tab-pane label="业务设置">
      <div class="panel settings-panel"><el-form :model="form" label-width="160">
        <el-form-item label="店铺名称"><el-input v-model="form.shop_name"/></el-form-item>
        <el-form-item label="默认单位"><el-input v-model="form.default_unit"/></el-form-item>
        <el-form-item label="允许负库存"><el-switch v-model="form.allow_negative_stock"/></el-form-item>
        <el-form-item label="滞销判定天数"><el-input-number v-model="form.stale_days" :min="1"/></el-form-item>
        <el-form-item><el-button type="primary" @click="save">保存设置</el-button></el-form-item>
      </el-form></div>
    </el-tab-pane>
    <el-tab-pane label="登录密码">
      <div class="panel settings-panel"><el-form :model="password" label-width="160">
        <el-form-item label="当前密码"><el-input v-model="password.current_password" type="password"/></el-form-item>
        <el-form-item label="新密码"><el-input v-model="password.new_password" type="password"/></el-form-item>
        <el-form-item><el-button type="primary" @click="changePassword">修改密码</el-button></el-form-item>
      </el-form></div>
    </el-tab-pane>
    <el-tab-pane label="备份恢复">
      <div class="page-actions"><span>恢复前会自动创建 pre_restore 快照。</span><el-button type="primary" @click="backup">立即备份</el-button></div>
      <div class="panel"><el-table :data="backups"><el-table-column prop="name" label="备份文件"/><el-table-column prop="created_at" label="创建时间"/><el-table-column prop="size" label="大小(字节)"/><el-table-column label="操作"><template #default="{row}"><el-button link type="danger" @click="restore(row)">恢复</el-button></template></el-table-column></el-table></div>
    </el-tab-pane>
  </el-tabs>
</template>
<style scoped>.settings-panel{max-width:680px;margin-top:12px}</style>
