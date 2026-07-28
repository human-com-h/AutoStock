import { newUlid } from "@autostock/shared";
import {
  db,
  getMeta,
  setMeta,
  type BusinessRow,
  type PartRow,
  type SyncHistoryRow,
  type SyncQueueRow,
} from "../db/schema";
import { apiRequest } from "./api";

type SyncTable =
  | "part"
  | "brand"
  | "category"
  | "supplier"
  | "customer"
  | "purchase_order"
  | "purchase_item"
  | "sales_order"
  | "sales_item"
  | "stock_ledger";

interface SyncChange {
  table: SyncTable;
  op: "insert" | "upsert" | "delete";
  row: Record<string, unknown>;
  client_updated_at: string;
}

interface PushResult {
  batch_id: string;
  accepted: number;
  rejected: Array<{ table: string; id: string; reason: string }>;
  conflicts: Array<Record<string, unknown>>;
  server_rev: number;
}

interface PullResult {
  changes: Array<{
    table: SyncTable;
    op: "upsert" | "delete";
    row: Record<string, unknown>;
    rev: number;
  }>;
  next_rev: number;
  has_more: boolean;
  snapshots: Array<Record<string, unknown>>;
}

interface PendingBatch {
  changes: SyncChange[];
  groups: Map<string, string[]>;
}

export interface SyncRunResult {
  pushed: number;
  pulled: number;
  conflicts: number;
  rejected: number;
  message: string;
}

function asChange(table: SyncTable, row: BusinessRow): SyncChange {
  return {
    table,
    op: row.is_deleted ? "delete" : table === "stock_ledger" ? "insert" : "upsert",
    row: { ...row },
    client_updated_at: row.updated_at,
  };
}

async function collectPendingBatch(): Promise<PendingBatch> {
  const queues = await db.syncQueue.orderBy("created_at").toArray();
  const changes = new Map<string, SyncChange>();
  const groups = new Map<string, string[]>();

  for (const queue of queues) {
    const groupKeys: string[] = [];
    if (queue.table_name === "purchase_order") {
      const order = await db.purchaseOrder.get(queue.row_id);
      if (!order) continue;
      const items = await db.purchaseItem.where("order_id").equals(order.id).toArray();
      const ledgers = items.length
        ? await db.stockLedger.where("source_id").anyOf(items.map((item) => item.id)).toArray()
        : [];
      const rows: Array<[SyncTable, BusinessRow]> = [
        ["purchase_order", order],
        ...items.map((row) => ["purchase_item", row] as [SyncTable, BusinessRow]),
        ...ledgers.map((row) => ["stock_ledger", row] as [SyncTable, BusinessRow]),
      ];
      for (const [table, row] of rows) {
        const key = `${table}:${row.id}`;
        changes.set(key, asChange(table, row));
        groupKeys.push(key);
      }
    } else {
      const order = await db.salesOrder.get(queue.row_id);
      if (!order) continue;
      const items = await db.salesItem.where("order_id").equals(order.id).toArray();
      const ledgers = items.length
        ? await db.stockLedger.where("source_id").anyOf(items.map((item) => item.id)).toArray()
        : [];
      const rows: Array<[SyncTable, BusinessRow]> = [
        ["sales_order", order],
        ...items.map((row) => ["sales_item", row] as [SyncTable, BusinessRow]),
        ...ledgers.map((row) => ["stock_ledger", row] as [SyncTable, BusinessRow]),
      ];
      for (const [table, row] of rows) {
        const key = `${table}:${row.id}`;
        changes.set(key, asChange(table, row));
        groupKeys.push(key);
      }
    }
    groups.set(queue.id, groupKeys);
  }
  return { changes: [...changes.values()], groups };
}

async function markSynced(table: SyncTable, id: string): Promise<void> {
  if (table === "purchase_order") await db.purchaseOrder.update(id, { sync_status: "synced" });
  if (table === "purchase_item") await db.purchaseItem.update(id, { sync_status: "synced" });
  if (table === "sales_order") await db.salesOrder.update(id, { sync_status: "synced" });
  if (table === "sales_item") await db.salesItem.update(id, { sync_status: "synced" });
  if (table === "stock_ledger") await db.stockLedger.update(id, { sync_status: "synced" });
}

async function applyPushResult(
  batch: PendingBatch,
  result: PushResult,
): Promise<void> {
  const rejected = new Set(result.rejected.map((row) => `${row.table}:${row.id}`));
  await db.transaction(
    "rw",
    [
      db.purchaseOrder,
      db.purchaseItem,
      db.salesOrder,
      db.salesItem,
      db.stockLedger,
      db.syncQueue,
      db.meta,
    ],
    async () => {
      for (const change of batch.changes) {
        const key = `${change.table}:${String(change.row.id)}`;
        if (!rejected.has(key)) await markSynced(change.table, String(change.row.id));
      }
      for (const [queueId, keys] of batch.groups) {
        if (keys.every((key) => !rejected.has(key))) {
          await db.syncQueue.delete(queueId);
        }
      }
      await db.meta.delete("sync_batch_id");
      await setMeta("last_server_rev", String(result.server_rev));
    },
  );
}

async function remapMergedPart(row: PartRow): Promise<void> {
  if (!row.merged_into) return;
  await db.purchaseItem.where("part_id").equals(row.id).modify({ part_id: row.merged_into });
  await db.salesItem.where("part_id").equals(row.id).modify({ part_id: row.merged_into });
  await db.stockLedger.where("part_id").equals(row.id).modify({ part_id: row.merged_into });
  await db.stockSnapshot.delete(row.id);
  await db.parts.delete(row.id);
}

async function applyServerChange(change: PullResult["changes"][number]): Promise<void> {
  const row = change.row;
  if (change.table === "part") {
    const part = row as unknown as PartRow;
    if (part.merged_into) await remapMergedPart(part);
    else await db.parts.put(part);
  } else if (change.table === "brand") {
    await db.brands.put(row as never);
  } else if (change.table === "category") {
    await db.categories.put(row as never);
  } else if (change.table === "supplier") {
    await db.suppliers.put(row as never);
  } else if (change.table === "customer") {
    await db.customers.put(row as never);
  } else if (change.table === "purchase_order") {
    await db.purchaseOrder.put({ ...row, sync_status: "synced" } as never);
  } else if (change.table === "purchase_item") {
    await db.purchaseItem.put({ ...row, sync_status: "synced" } as never);
  } else if (change.table === "sales_order") {
    await db.salesOrder.put({ ...row, sync_status: "synced" } as never);
  } else if (change.table === "sales_item") {
    await db.salesItem.put({ ...row, sync_status: "synced" } as never);
  } else if (change.table === "stock_ledger") {
    await db.stockLedger.put({ ...row, sync_status: "synced" } as never);
  }
}

async function applyPullPage(page: PullResult): Promise<void> {
  await db.transaction(
    "rw",
    [
      db.parts,
      db.brands,
      db.categories,
      db.suppliers,
      db.customers,
      db.purchaseOrder,
      db.purchaseItem,
      db.salesOrder,
      db.salesItem,
      db.stockLedger,
      db.stockSnapshot,
      db.meta,
    ],
    async () => {
      for (const change of page.changes) await applyServerChange(change);
      await db.stockSnapshot.bulkPut(
        page.snapshots.map((row) => ({
          ...row,
          quantity: Number(row.quantity || 0),
          avg_cost: Number(row.avg_cost || 0),
          updated_at: new Date().toISOString(),
        })) as never[],
      );
      await setMeta("last_pull_rev", String(page.next_rev));
    },
  );
}

async function addHistory(
  startedAt: string,
  result: Omit<SyncHistoryRow, "id" | "started_at" | "finished_at">,
): Promise<void> {
  await db.syncHistory.add({
    id: newUlid(),
    started_at: startedAt,
    finished_at: new Date().toISOString(),
    ...result,
  });
}

let activeSync: Promise<SyncRunResult> | null = null;

export function synchronize(): Promise<SyncRunResult> {
  if (activeSync) return activeSync;
  activeSync = runSynchronization().finally(() => {
    activeSync = null;
  });
  return activeSync;
}

async function runSynchronization(): Promise<SyncRunResult> {
  const startedAt = new Date().toISOString();
  let pushed = 0;
  let pulled = 0;
  let conflicts = 0;
  let rejected = 0;
  try {
    const deviceId = await getMeta("device_id");
    if (!deviceId) throw new Error("手机尚未与电脑配对");
    const batch = await collectPendingBatch();
    if (batch.changes.length) {
      let batchId = await getMeta("sync_batch_id");
      if (!batchId) {
        batchId = newUlid();
        await setMeta("sync_batch_id", batchId);
      }
      const push = await apiRequest<PushResult>("/api/sync/push", {
        method: "POST",
        body: JSON.stringify({
          device_id: deviceId,
          client_batch_id: batchId,
          changes: batch.changes,
        }),
      });
      await applyPushResult(batch, push);
      pushed = push.accepted;
      conflicts += push.conflicts.length;
      rejected += push.rejected.length;
    } else {
      await db.meta.delete("sync_batch_id");
    }

    let cursor = Number((await getMeta("last_pull_rev")) || 0);
    while (true) {
      const page = await apiRequest<PullResult>(
        `/api/sync/pull?since_rev=${cursor}&limit=500`,
      );
      await applyPullPage(page);
      pulled += page.changes.length;
      cursor = page.next_rev;
      if (!page.has_more) break;
    }
    const now = new Date().toISOString();
    await setMeta("last_sync_at", now);
    const message = rejected
      ? `同步完成，但有 ${rejected} 项需要处理`
      : `已上传 ${pushed} 项、下载 ${pulled} 项`;
    await addHistory(startedAt, {
      pushed_count: pushed,
      pulled_count: pulled,
      conflict_count: conflicts,
      rejected_count: rejected,
      result: rejected ? "partial" : "success",
      message,
    });
    return { pushed, pulled, conflicts, rejected, message };
  } catch (error) {
    const message = error instanceof Error ? error.message : "同步失败";
    await addHistory(startedAt, {
      pushed_count: pushed,
      pulled_count: pulled,
      conflict_count: conflicts,
      rejected_count: rejected,
      result: "failed",
      message,
    });
    throw error;
  }
}

export async function recentSyncHistory(limit = 30): Promise<SyncHistoryRow[]> {
  return db.syncHistory.orderBy("started_at").reverse().limit(limit).toArray();
}
