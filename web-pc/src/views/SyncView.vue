<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { http } from "../api";

const summary = ref({ devices: 0, enabled_devices: 0, unresolved_conflicts: 0, logs: 0 });
const devices = ref<any[]>([]);
const conflicts = ref<any[]>([]);
const logs = ref<any[]>([]);
const loading = ref(false);

function formatTime(value: string | null): string {
  return value?.replace("T", " ").slice(0, 19) || "—";
}

function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

async function load(): Promise<void> {
  loading.value = true;
  try {
    const [summaryData, deviceRows, conflictRows, logRows] = await Promise.all([
      http.get("/sync/summary"),
      http.get("/devices"),
      http.get("/sync/conflicts", { params: { limit: 200 } }),
      http.get("/sync/logs", { params: { limit: 200 } }),
    ]);
    summary.value = summaryData as unknown as typeof summary.value;
    devices.value = deviceRows as unknown as any[];
    conflicts.value = conflictRows as unknown as any[];
    logs.value = logRows as unknown as any[];
  } finally {
    loading.value = false;
  }
}

async function toggleDevice(row: any): Promise<void> {
  await http.put(`/devices/${row.id}`, { is_enabled: Boolean(row.is_enabled) });
  ElMessage.success(row.is_enabled ? "设备已启用" : "设备已停用，原令牌立即失效");
  await load();
}

async function resolve(row: any, action: "keep_current" | "restore_local" | "restore_remote"): Promise<void> {
  const labels = {
    keep_current: "保留当前数据并确认",
    restore_local: "回填冲突发生前的 PC 数据",
    restore_remote: "回填手机推送的数据",
  };
  await ElMessageBox.confirm(`确定${labels[action]}？`, "冲突复核", { type: "warning" });
  await http.post(`/sync/conflicts/${row.id}/resolve`, { action });
  ElMessage.success("冲突已复核");
  await load();
}

onMounted(load);
</script>

<template>
  <div v-loading="loading">
    <div class="summary-grid">
      <div><small>已登记设备</small><strong>{{ summary.devices }}</strong></div>
      <div><small>启用设备</small><strong>{{ summary.enabled_devices }}</strong></div>
      <div><small>待复核冲突</small><strong :class="{ alert: summary.unresolved_conflicts }">{{ summary.unresolved_conflicts }}</strong></div>
      <div><small>同步批次</small><strong>{{ summary.logs }}</strong></div>
    </div>

    <el-tabs class="sync-tabs">
      <el-tab-pane label="设备管理">
        <div class="panel">
          <el-table :data="devices">
            <el-table-column prop="name" label="设备名称" min-width="180" />
            <el-table-column prop="device_type" label="类型" width="100" />
            <el-table-column label="最后同步" min-width="180">
              <template #default="{ row }">{{ formatTime(row.last_sync_at) }}</template>
            </el-table-column>
            <el-table-column prop="last_pull_rev" label="拉取游标" width="120" />
            <el-table-column label="启用" width="100">
              <template #default="{ row }">
                <el-switch v-model="row.is_enabled" :active-value="1" :inactive-value="0" @change="toggleDevice(row)" />
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane :label="`冲突复核（${summary.unresolved_conflicts}）`">
        <div class="panel">
          <el-table :data="conflicts" row-key="id">
            <el-table-column type="expand">
              <template #default="{ row }">
                <div class="conflict-detail">
                  <section><h4>PC / Hub 快照</h4><pre>{{ formatJson(row.local_value) }}</pre></section>
                  <section><h4>手机推送快照</h4><pre>{{ formatJson(row.remote_value) }}</pre></section>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="table_name" label="数据表" width="140" />
            <el-table-column prop="row_id" label="记录 ID" min-width="220" />
            <el-table-column prop="conflict_type" label="原因" width="180" />
            <el-table-column prop="resolution" label="自动处理" width="120" />
            <el-table-column label="时钟偏差" width="100">
              <template #default="{ row }">{{ row.clock_skew ? "是" : "否" }}</template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.resolved_at ? 'success' : 'warning'">{{ row.resolved_at ? "已复核" : "待复核" }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" min-width="260">
              <template #default="{ row }">
                <template v-if="!row.resolved_at">
                  <el-button link type="primary" @click="resolve(row, 'keep_current')">确认当前值</el-button>
                  <el-button link @click="resolve(row, 'restore_local')">回填 PC 值</el-button>
                  <el-button link type="warning" @click="resolve(row, 'restore_remote')">回填手机值</el-button>
                </template>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="同步历史">
        <div class="panel">
          <el-table :data="logs">
            <el-table-column label="开始时间" min-width="180"><template #default="{ row }">{{ formatTime(row.started_at) }}</template></el-table-column>
            <el-table-column prop="direction" label="方向" width="90" />
            <el-table-column prop="pushed_count" label="上传" width="90" />
            <el-table-column prop="pulled_count" label="下载" width="90" />
            <el-table-column prop="conflict_count" label="冲突" width="90" />
            <el-table-column label="rev 区间" min-width="150"><template #default="{ row }">{{ row.from_rev }} → {{ row.to_rev }}</template></el-table-column>
            <el-table-column label="结果" width="100">
              <template #default="{ row }">
                <el-tag :type="row.result === 'success' ? 'success' : row.result === 'partial' ? 'warning' : 'danger'">{{ row.result }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="message" label="摘要" min-width="220" />
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(150px, 1fr)); gap: 14px; }
.summary-grid > div { padding: 18px 20px; background: white; border: 1px solid #e2e7ef; border-radius: 8px; }
.summary-grid small, .summary-grid strong { display: block; }
.summary-grid small { color: #657186; }
.summary-grid strong { margin-top: 8px; font-size: 28px; }
.summary-grid strong.alert { color: #e3841f; }
.sync-tabs { margin-top: 18px; }
.conflict-detail { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; padding: 8px 34px 18px; }
.conflict-detail h4 { margin: 0 0 8px; }
.conflict-detail pre { max-height: 300px; margin: 0; padding: 13px; overflow: auto; background: #f5f7fb; border-radius: 6px; white-space: pre-wrap; word-break: break-all; }
@media (max-width: 1000px) {
  .summary-grid { grid-template-columns: repeat(2, 1fr); }
  .conflict-detail { grid-template-columns: 1fr; }
}
</style>
