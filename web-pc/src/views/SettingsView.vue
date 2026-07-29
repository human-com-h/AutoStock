<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { Delete, Plus } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { http } from "../api";

type PrintCustomField = {
  label: string;
  value: string;
  visible: boolean;
  handwritten: boolean;
};

const form = reactive({
  shop_name: "",
  default_unit: "个",
  allow_negative_stock: true,
  stale_days: 180,
  shop_phone: "",
  shop_address: "",
  business_scope: "",
  print_notice: "商品如有质量问题，请及时联系我们处理。",
  print_warehouse: "主仓库",
  print_operator: "管理员",
  settlement_method: "现结",
  print_payment_account: "",
  print_wechat: "",
  print_warranty_period: "",
  print_reviewer: "",
  print_custom_fields: [] as PrintCustomField[],
});
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
  const settings = await http.get("/settings") as unknown as typeof form;
  Object.assign(form, settings);
  form.print_custom_fields = Array.isArray(settings.print_custom_fields)
    ? settings.print_custom_fields.map((field) => ({ ...field }))
    : [];
  backups.value = await http.get("/backups") as unknown as any[];
}
function addPrintField() {
  if (form.print_custom_fields.length >= 5) {
    ElMessage.warning("最多添加 5 个自定义字段");
    return;
  }
  form.print_custom_fields.push({
    label: "",
    value: "",
    visible: true,
    handwritten: true,
  });
}
function removePrintField(index: number) {
  form.print_custom_fields.splice(index, 1);
}
async function save() {
  const printCustomFields = form.print_custom_fields.map((field) => ({
    ...field,
    label: field.label.trim(),
    value: field.value.trim(),
  }));
  if (printCustomFields.some((field) => !field.label)) {
    ElMessage.warning("请填写自定义字段名称，或删除空白字段");
    return;
  }
  Object.assign(
    form,
    await http.put("/settings", {
      ...form,
      print_custom_fields: printCustomFields,
    }),
  );
  ElMessage.success("系统设置已保存");
}
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
        <el-divider content-position="left">单据打印抬头</el-divider>
        <el-form-item label="店铺电话"><el-input v-model="form.shop_phone" placeholder="显示在单据底部"/></el-form-item>
        <el-form-item label="店铺地址"><el-input v-model="form.shop_address" placeholder="显示在单据底部"/></el-form-item>
        <el-form-item label="发货/入库仓库"><el-input v-model="form.print_warehouse"/></el-form-item>
        <el-form-item label="默认制单人"><el-input v-model="form.print_operator"/></el-form-item>
        <el-form-item label="默认复核人"><el-input v-model="form.print_reviewer" placeholder="留空时打印横线"/></el-form-item>
        <el-form-item label="默认结算方式"><el-input v-model="form.settlement_method"/></el-form-item>
        <el-form-item label="经营项目">
          <el-input v-model="form.business_scope" type="textarea" :rows="2" placeholder="例如：制动片、离合器片、轴承等"/>
        </el-form-item>
        <el-form-item label="打印说明">
          <el-input v-model="form.print_notice" type="textarea" :rows="2"/>
        </el-form-item>
        <el-divider content-position="left">收款与售后信息</el-divider>
        <el-form-item label="开户行/收款账户">
          <el-input
            v-model="form.print_payment_account"
            type="textarea"
            :rows="2"
            placeholder="例如：工商银行 6222 **** **** 1234 户名：张三"
          />
        </el-form-item>
        <el-form-item label="联系微信">
          <el-input v-model="form.print_wechat" placeholder="留空则不在单据中显示"/>
        </el-form-item>
        <el-form-item label="售后期限">
          <el-input v-model="form.print_warranty_period" placeholder="例如：三包期内凭本单退换"/>
        </el-form-item>

        <el-divider content-position="left">
          <div class="custom-divider">
            <span>自定义打印字段（最多 5 项）</span>
            <el-button
              size="small"
              plain
              :icon="Plus"
              :disabled="form.print_custom_fields.length >= 5"
              @click="addPrintField"
            >
              添加字段
            </el-button>
          </div>
        </el-divider>
        <p class="custom-field-tip">
          “留空手写”会在打印件上显示横线，不会修改或补写历史单据数据。
        </p>
        <div v-if="form.print_custom_fields.length" class="custom-field-list">
          <div
            v-for="(field, index) in form.print_custom_fields"
            :key="index"
            class="custom-field-card"
          >
            <div class="custom-field-inputs">
              <el-input
                v-model="field.label"
                maxlength="20"
                placeholder="字段名称，如物流单号"
              />
              <el-input
                v-model="field.value"
                maxlength="100"
                :disabled="field.handwritten"
                :placeholder="field.handwritten ? '打印时显示手写横线' : '默认打印内容'"
              />
            </div>
            <div class="custom-field-options">
              <el-switch v-model="field.visible" active-text="显示"/>
              <el-checkbox v-model="field.handwritten">留空手写</el-checkbox>
              <el-button
                text
                type="danger"
                :icon="Delete"
                aria-label="删除自定义字段"
                @click="removePrintField(index)"
              />
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无自定义字段" :image-size="54"/>
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
.settings-panel{max-width:860px;margin-top:12px}
.custom-divider{display:flex;width:100%;align-items:center;justify-content:space-between;gap:12px}
.custom-field-tip{margin:-4px 0 12px 160px;color:#7b8798;font-size:13px;line-height:1.6}
.custom-field-list{margin:0 0 18px 160px}
.custom-field-card{display:flex;align-items:center;gap:14px;margin-bottom:10px;padding:12px;border:1px solid #e1e6ed;border-radius:8px;background:#fafbfc}
.custom-field-inputs{display:grid;flex:1;grid-template-columns:minmax(160px,.65fr) minmax(220px,1.35fr);gap:10px}
.custom-field-options{display:flex;flex:none;align-items:center;gap:12px}
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
@media(max-width:760px){
  .custom-field-tip,.custom-field-list{margin-left:0}
  .custom-field-card{align-items:stretch;flex-direction:column}
  .custom-field-inputs{grid-template-columns:1fr}
  .custom-field-options{justify-content:space-between}
}
</style>
