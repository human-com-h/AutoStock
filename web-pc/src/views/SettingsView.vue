<script setup lang="ts">
import { reactive } from "vue"; import { ElMessage } from "element-plus";
const form=reactive({shop_name:"AutoStock 汽配店",allow_negative_stock:true,stale_days:180});
function save(){localStorage.setItem("autostock-ui-settings",JSON.stringify(form));ElMessage.success("界面设置已保存")}
</script>
<template><div class="panel" style="max-width:680px"><el-form :model="form" label-width="160"><el-form-item label="店铺名称"><el-input v-model="form.shop_name"/></el-form-item><el-form-item label="允许负库存"><el-switch v-model="form.allow_negative_stock"/></el-form-item><el-form-item label="滞销判定天数"><el-input-number v-model="form.stale_days" :min="1"/></el-form-item><el-form-item><el-button type="primary" @click="save">保存设置</el-button></el-form-item></el-form></div></template>
