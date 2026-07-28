<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { http } from "../api";

const form = reactive({ shop_name: "", default_unit: "个", allow_negative_stock: true, stale_days: 180 });
const backups = ref<any[]>([]);
const password = reactive({ current_password: "", new_password: "" });
const pairing = ref<any | null>(null);
const pairingLoading = ref(false);
const pairingUrl = computed(() => pairing.value?.pairing_urls?.[0] || "");
const pairingQrSrc = computed(() =>
  pairingUrl.value
    ? `/api/pairing/qr?content=${encodeURIComponent(pairingUrl.value)}`
    : "",
);
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
async function createPairingCode() {
  pairingLoading.value = true;
  try {
    pairing.value = await http.post("/pairing/code");
    ElMessage.success("配对码已生成，5 分钟内有效");
  } finally {
    pairingLoading.value = false;
  }
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
    <el-tab-pane label="手机配对">
      <div class="pairing-layout">
        <div class="panel pairing-panel">
          <h3>连接 Android 手机</h3>
          <p class="pairing-intro">手机与电脑连接同一 WiFi 后，先安装本地 CA，再用系统相机扫描配对二维码。</p>
          <el-button type="primary" :loading="pairingLoading" @click="createPairingCode">
            生成配对二维码
          </el-button>
          <div v-if="pairing" class="pairing-result">
            <img :src="pairingQrSrc" alt="AutoStock 手机配对二维码" />
            <div>
              <small>6 位配对码</small>
              <strong>{{ pairing.code }}</strong>
              <p>也可在手机引导页手动输入。</p>
              <a :href="pairing.ca_download_urls?.[0]" target="_blank">下载 CA 证书</a>
              <code>{{ pairingUrl }}</code>
            </div>
          </div>
        </div>
        <div class="panel android-guide">
          <h3>Android 安装步骤</h3>
          <ol>
            <li>在手机浏览器下载 <code>ca.crt</code>。</li>
            <li>设置 → 安全 → 加密与凭据 → 安装证书 → CA 证书。</li>
            <li>选择 ca.crt，确认安装 AutoStock Local CA。</li>
            <li>用系统相机扫描二维码，打开 HTTPS 页面并点击“检测一下”。</li>
            <li>初始化完成后，在 Chrome 菜单中选择“添加到主屏幕”。</li>
          </ol>
          <el-alert type="warning" :closable="false" show-icon>
            CA 私钥只保存在本机且不会进入业务备份。不再使用时可从手机系统设置删除该 CA。
          </el-alert>
        </div>
      </div>
    </el-tab-pane>
  </el-tabs>
</template>
<style scoped>
.settings-panel{max-width:680px;margin-top:12px}
.pairing-layout{display:grid;grid-template-columns:minmax(430px,1.2fr) minmax(320px,.8fr);gap:16px}
.pairing-panel h3,.android-guide h3{margin-top:0}
.pairing-intro{color:#657186;line-height:1.6}
.pairing-result{display:grid;grid-template-columns:220px 1fr;gap:22px;align-items:center;margin-top:20px;padding-top:20px;border-top:1px solid #e5eaf2}
.pairing-result img{width:220px;height:220px;border:1px solid #dbe3ee;border-radius:10px}
.pairing-result small,.pairing-result strong,.pairing-result code{display:block}
.pairing-result strong{margin:8px 0;font-size:36px;letter-spacing:.15em;color:#2f6bff}
.pairing-result p{color:#657186;font-size:13px}
.pairing-result code{margin-top:12px;padding:9px;background:#f4f7fb;border-radius:6px;font-size:11px;overflow-wrap:anywhere}
.android-guide ol{padding-left:20px;color:#394a61;line-height:2}
@media(max-width:1000px){.pairing-layout{grid-template-columns:1fr}}
</style>
