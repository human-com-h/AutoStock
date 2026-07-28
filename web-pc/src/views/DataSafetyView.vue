<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { http } from "../api";

type HistoryRow = {
  id: string;
  action: string;
  entity_type: string;
  entity_type_label: string;
  entity_label: string;
  summary: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  actor: string;
  created_at: string;
  can_restore: boolean;
};

type BackupRow = {
  name: string;
  label?: string;
  reason: string;
  created_at: string;
  size: number;
  verified: boolean;
  summary?: {
    parts?: number;
    purchase_orders?: number;
    sales_orders?: number;
    stock_quantity?: number;
  };
};

type RetentionRow = {
  type: string;
  label: string;
  days: number;
  max_count: number;
};

const historyRows = ref<HistoryRow[]>([]);
const backups = ref<BackupRow[]>([]);
const retentionRows = ref<RetentionRow[]>([]);
const loading = ref(false);
const creatingBackup = ref(false);
const exporting = ref(false);
const importing = ref(false);
const selectedPackage = ref<File | null>(null);
const detailVisible = ref(false);
const detail = ref<HistoryRow | null>(null);
const filters = reactive({ entity_type: "", action: "" });

const actionLabels: Record<string, string> = {
  create: "新建",
  update: "修改",
  delete: "删除",
  deactivate: "停用",
  restore: "恢复版本",
  void: "撤销",
  reverse: "红冲",
  return: "退货",
};

const reasonLabels: Record<string, string> = {
  manual: "手动创建",
  daily_startup: "每日自动",
  legacy: "旧版备份",
};

const detailFields = computed(() => {
  const keys = new Set([
    ...Object.keys(detail.value?.before || {}),
    ...Object.keys(detail.value?.after || {}),
  ]);
  const hidden = new Set(["id", "created_at", "updated_at", "rev", "version", "device_id"]);
  return [...keys]
    .filter((key) => !hidden.has(key))
    .map((key) => ({
      key,
      before: detail.value?.before?.[key],
      after: detail.value?.after?.[key],
    }));
});

function formatTime(value: string) {
  return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "—";
}

function formatSize(value: number) {
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function formatValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

function backupReason(row: BackupRow) {
  if (row.reason.startsWith("before_restore:")) return "恢复前保护";
  if (row.reason.startsWith("before_sync:")) return "同步前保护";
  if (row.reason === "before_migration_import") return "迁移前保护";
  return reasonLabels[row.reason] || row.reason;
}

async function loadHistory() {
  const params: Record<string, string | number> = { limit: 300 };
  if (filters.entity_type) params.entity_type = filters.entity_type;
  if (filters.action) params.action = filters.action;
  historyRows.value = (await http.get("/history", { params })) as unknown as HistoryRow[];
}

async function loadBackups() {
  const [backupData, retentionData] = await Promise.all([
    http.get("/backups"),
    http.get("/backups/retention-policy"),
  ]);
  backups.value = backupData as unknown as BackupRow[];
  retentionRows.value = retentionData as unknown as RetentionRow[];
}

async function load() {
  loading.value = true;
  try {
    await Promise.all([loadHistory(), loadBackups()]);
  } finally {
    loading.value = false;
  }
}

function showDetail(row: HistoryRow) {
  detail.value = row;
  detailVisible.value = true;
}

async function restoreVersion(row: HistoryRow) {
  await ElMessageBox.confirm(
    `将「${row.entity_label}」恢复到这次操作之前的版本。恢复动作会留下新的历史记录，确定继续吗？`,
    "恢复历史版本",
    { type: "warning", confirmButtonText: "恢复此版本" },
  );
  await http.post(`/history/${row.id}/restore`, { confirm: "RESTORE" });
  ElMessage.success("历史版本已恢复");
  detailVisible.value = false;
  await loadHistory();
}

async function createRestorePoint() {
  const result = await ElMessageBox.prompt(
    "建议填写容易识别的名称，例如“月底盘点前”或“批量导入前”。",
    "创建还原点",
    { inputPlaceholder: "还原点备注（可留空）", confirmButtonText: "立即创建" },
  );
  creatingBackup.value = true;
  try {
    await http.post("/backups", { label: result.value || null });
    await loadBackups();
    ElMessage.success("还原点已创建并通过完整性检查");
  } finally {
    creatingBackup.value = false;
  }
}

async function restoreBackup(row: BackupRow) {
  const summary = row.summary || {};
  await ElMessageBox.confirm(
    `确定将整套数据恢复到“${row.label || row.name}”吗？该还原点包含 ${
      summary.parts || 0
    } 个零件、${summary.purchase_orders || 0} 张采购单和 ${
      summary.sales_orders || 0
    } 张销售单。当前数据会先自动创建保护点。`,
    "整库恢复",
    {
      type: "error",
      confirmButtonText: "确认整库恢复",
      distinguishCancelAndClose: true,
    },
  );
  await http.post("/backups/restore", { name: row.name, confirm: "RESTORE" });
  ElMessage.success("整库恢复完成，正在刷新页面");
  window.setTimeout(() => window.location.reload(), 800);
}

async function exportPackage() {
  exporting.value = true;
  try {
    const blob = (await http.get("/backups/migration/export", {
      responseType: "blob",
      timeout: 10 * 60 * 1000,
    })) as unknown as Blob;
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    const stamp = new Date().toISOString().slice(0, 19).replace(/[T:]/g, "-");
    anchor.href = url;
    anchor.download = `AutoStock_${stamp}_经营数据.zip`;
    anchor.click();
    URL.revokeObjectURL(url);
    ElMessage.success("迁移包已生成");
  } finally {
    exporting.value = false;
  }
}

function choosePackage(event: Event) {
  const input = event.target as HTMLInputElement;
  selectedPackage.value = input.files?.[0] || null;
}

async function importPackage() {
  if (!selectedPackage.value) {
    ElMessage.warning("请先选择 AutoStock 迁移包");
    return;
  }
  await ElMessageBox.confirm(
    `将导入“${selectedPackage.value.name}”。系统会先校验文件、升级旧版结构、核对库存，并自动备份当前数据。确定继续吗？`,
    "导入迁移包",
    { type: "warning", confirmButtonText: "校验并导入" },
  );
  importing.value = true;
  try {
    await http.post("/backups/migration/import", selectedPackage.value, {
      headers: { "Content-Type": "application/zip" },
      timeout: 10 * 60 * 1000,
    });
    ElMessage.success("迁移包导入成功，正在刷新页面");
    window.setTimeout(() => window.location.reload(), 800);
  } finally {
    importing.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div v-loading="loading" class="safety-page">
    <el-alert
      title="日常误操作优先恢复单条资料或对单据做撤销/红冲；只有严重问题才使用整库恢复。"
      type="info"
      :closable="false"
      show-icon
    />

    <el-tabs class="safety-tabs">
      <el-tab-pane label="操作历史">
        <div class="toolbar">
          <div class="filters">
            <el-select
              v-model="filters.entity_type"
              clearable
              placeholder="全部资料与单据"
              @change="loadHistory"
            >
              <el-option label="零件" value="part" />
              <el-option label="分类" value="category" />
              <el-option label="品牌" value="brand" />
              <el-option label="供应商" value="supplier" />
              <el-option label="客户" value="customer" />
              <el-option label="采购单" value="purchase_order" />
              <el-option label="销售单" value="sales_order" />
            </el-select>
            <el-select
              v-model="filters.action"
              clearable
              placeholder="全部操作"
              @change="loadHistory"
            >
              <el-option
                v-for="(label, value) in actionLabels"
                :key="value"
                :label="label"
                :value="value"
              />
            </el-select>
          </div>
          <el-button @click="loadHistory">刷新</el-button>
        </div>
        <div class="panel table-panel">
          <el-table :data="historyRows" empty-text="尚无操作历史">
            <el-table-column prop="created_at" label="时间" width="180">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column prop="entity_type_label" label="类型" width="95" />
            <el-table-column prop="entity_label" label="对象" min-width="150" />
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-tag effect="plain">{{ actionLabels[row.action] || row.action }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="summary" label="说明" min-width="280" />
            <el-table-column label="操作" width="170" fixed="right">
              <template #default="{ row }">
                <el-button link @click="showDetail(row)">查看变化</el-button>
                <el-button
                  v-if="row.can_restore"
                  link
                  type="primary"
                  @click="restoreVersion(row)"
                >
                  恢复操作前版本
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="还原点">
        <div class="toolbar">
          <div>
            <strong>整库还原点</strong>
            <span class="hint">恢复时会先自动保存当前数据，并再次核对库存。</span>
          </div>
          <el-button type="primary" :loading="creatingBackup" @click="createRestorePoint">
            创建还原点
          </el-button>
        </div>
        <div class="retention-strip">
          <span>自动清理规则：</span>
          <el-tag v-for="row in retentionRows" :key="row.type" effect="plain">
            {{ row.label }} {{ row.days }} 天 / 最多 {{ row.max_count }} 个
          </el-tag>
        </div>
        <div class="panel table-panel">
          <el-table :data="backups" empty-text="尚无还原点">
            <el-table-column label="名称" min-width="210">
              <template #default="{ row }">
                <strong>{{ row.label || row.name }}</strong>
                <small v-if="row.label">{{ row.name }}</small>
              </template>
            </el-table-column>
            <el-table-column label="来源" width="120">
              <template #default="{ row }">{{ backupReason(row) }}</template>
            </el-table-column>
            <el-table-column label="创建时间" width="180">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="数据摘要" min-width="240">
              <template #default="{ row }">
                零件 {{ row.summary?.parts || 0 }} · 采购单
                {{ row.summary?.purchase_orders || 0 }} · 销售单
                {{ row.summary?.sales_orders || 0 }} · 库存
                {{ row.summary?.stock_quantity || 0 }}
              </template>
            </el-table-column>
            <el-table-column label="校验" width="90">
              <template #default="{ row }">
                <el-tag :type="row.verified ? 'success' : 'warning'" effect="plain">
                  {{ row.verified ? "已验证" : "旧备份" }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="大小" width="100">
              <template #default="{ row }">{{ formatSize(row.size) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button link type="danger" @click="restoreBackup(row)">整库恢复</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="备份与迁移">
        <div class="migration-grid">
          <section class="panel migration-card">
            <div class="card-title">
              <span class="step">1</span>
              <div>
                <h3>导出经营数据迁移包</h3>
                <p>适用于备份到 U 盘、换电脑迁移或长期归档。</p>
              </div>
            </div>
            <ul>
              <li><strong>autostock.db</strong>：供 AutoStock 无损恢复</li>
              <li><strong>经营数据.xlsx</strong>：中文工作表，金额以元显示</li>
              <li><strong>CSV</strong>：零件、库存、单据、流水、客户和供应商</li>
              <li><strong>校验文件</strong>：防止拷贝损坏或内容被修改</li>
            </ul>
            <el-button type="primary" :loading="exporting" @click="exportPackage">
              导出完整迁移包
            </el-button>
          </section>

          <section class="panel migration-card">
            <div class="card-title">
              <span class="step">2</span>
              <div>
                <h3>在本机导入迁移包</h3>
                <p>导入前自动创建当前数据保护点，失败不会替换现有数据。</p>
              </div>
            </div>
            <label class="file-picker">
              <input type="file" accept=".zip,application/zip" @change="choosePackage" />
              <span>{{ selectedPackage?.name || "选择 AutoStock ZIP 迁移包" }}</span>
            </label>
            <el-button
              type="warning"
              :disabled="!selectedPackage"
              :loading="importing"
              @click="importPackage"
            >
              校验并导入
            </el-button>
          </section>
        </div>
        <el-alert
          class="migration-note"
          title="迁移包不包含本机 HTTPS 证书和 CA 私钥。换电脑后需要重新生成证书并让手机重新配对。"
          type="warning"
          :closable="false"
          show-icon
        />
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="detailVisible" title="操作变化" width="760px">
      <div v-if="detail" class="detail-head">
        <strong>{{ detail.summary }}</strong>
        <span>{{ formatTime(detail.created_at) }} · {{ detail.actor }}</span>
      </div>
      <el-table :data="detailFields" max-height="480">
        <el-table-column prop="key" label="字段" width="170" />
        <el-table-column label="操作前">
          <template #default="{ row }">
            <pre>{{ formatValue(row.before) }}</pre>
          </template>
        </el-table-column>
        <el-table-column label="操作后">
          <template #default="{ row }">
            <pre>{{ formatValue(row.after) }}</pre>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button
          v-if="detail?.can_restore"
          type="primary"
          @click="restoreVersion(detail)"
        >
          恢复操作前版本
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.safety-tabs { margin-top: 18px; }
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 14px;
}
.filters { display: flex; gap: 10px; }
.filters .el-select { width: 190px; }
.hint { margin-left: 12px; color: #718096; font-size: 13px; }
.retention-strip {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin: -2px 0 14px;
  color: #718096;
  font-size: 13px;
}
.table-panel { padding: 0; overflow: hidden; }
.table-panel small { display: block; margin-top: 4px; color: #8994a6; }
.migration-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.migration-card { min-height: 330px; display: flex; flex-direction: column; align-items: flex-start; }
.card-title { display: flex; gap: 14px; }
.card-title h3 { margin: 3px 0 6px; }
.card-title p { margin: 0; color: #718096; line-height: 1.5; }
.step {
  flex: none;
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: #eaf1ff;
  color: #2f6bff;
  font-weight: 700;
}
.migration-card ul { margin: 24px 0; padding-left: 20px; color: #48566a; line-height: 2; }
.migration-card > .el-button { margin-top: auto; }
.file-picker {
  width: 100%;
  margin: 34px 0 18px;
  padding: 24px;
  border: 1px dashed #a9b7ca;
  border-radius: 8px;
  background: #f8fafc;
  color: #2f6bff;
  text-align: center;
  cursor: pointer;
}
.file-picker input { display: none; }
.migration-note { margin-top: 18px; }
.detail-head { display: flex; justify-content: space-between; margin-bottom: 14px; }
.detail-head span { color: #718096; font-size: 13px; }
pre { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; }
@media (max-width: 1000px) {
  .migration-grid { grid-template-columns: 1fr; }
}
</style>
