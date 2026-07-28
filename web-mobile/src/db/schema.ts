import Dexie, { type EntityTable } from "dexie";

export type SyncStatus = "pending" | "synced";

export interface BusinessRow {
  id: string;
  created_at: string;
  updated_at: string;
  rev: number;
  version: number;
  device_id: string;
  is_deleted: number;
}

export interface PartRow extends BusinessRow {
  part_number: string;
  oe_number: string | null;
  name: string;
  spec: string | null;
  brand_id: string | null;
  category_id: string | null;
  supplier_id: string | null;
  unit: string;
  purchase_price: number;
  sale_price: number;
  min_stock: number;
  max_stock: number | null;
  location: string | null;
  vehicle_models: string | null;
  pinyin: string | null;
  remark: string | null;
  is_active: number;
  merged_into?: string | null;
}

export interface StockSnapshotRow {
  part_id: string;
  quantity: number;
  avg_cost: number;
  last_in_at: string | null;
  last_out_at: string | null;
  calc_rev?: number;
  updated_at: string;
}

export interface PurchaseOrderRow extends BusinessRow {
  order_no: string;
  supplier_id: string | null;
  order_date: string;
  total_amount: number;
  paid_amount: number;
  order_type: string;
  source_order_id: string | null;
  reversed_by: string | null;
  remark: string | null;
  sync_status: SyncStatus;
}

export interface PurchaseItemRow extends BusinessRow {
  order_id: string;
  part_id: string;
  quantity: number;
  purchase_price: number;
  amount: number;
  remark: string | null;
  sync_status: SyncStatus;
}

export interface SalesOrderRow extends BusinessRow {
  order_no: string;
  customer_id: string | null;
  customer_name: string | null;
  order_date: string;
  total_amount: number;
  received_amount: number;
  order_type: string;
  source_order_id: string | null;
  reversed_by: string | null;
  remark: string | null;
  sync_status: SyncStatus;
}

export interface SalesItemRow extends BusinessRow {
  order_id: string;
  part_id: string;
  quantity: number;
  sale_price: number;
  amount: number;
  cost_amount: number;
  remark: string | null;
  sync_status: SyncStatus;
}

export interface StockLedgerRow extends BusinessRow {
  part_id: string;
  change_type: string;
  quantity: number;
  unit_cost: number;
  source_type: string;
  source_id: string;
  occurred_at: string;
  remark: string | null;
  sync_status: SyncStatus;
}

export interface SyncQueueRow {
  id: string;
  table_name: "purchase_order" | "sales_order";
  row_id: string;
  op: "insert";
  created_at: string;
}

export interface SyncHistoryRow {
  id: string;
  started_at: string;
  finished_at: string;
  pushed_count: number;
  pulled_count: number;
  conflict_count: number;
  rejected_count: number;
  result: "success" | "partial" | "failed";
  message: string;
}

export interface MetaRow {
  key: string;
  value: string;
}

export interface NamedRow extends BusinessRow {
  name: string;
  is_active: number;
  [key: string]: unknown;
}

class AutoStockMobileDB extends Dexie {
  parts!: EntityTable<PartRow, "id">;
  stockSnapshot!: EntityTable<StockSnapshotRow, "part_id">;
  salesOrder!: EntityTable<SalesOrderRow, "id">;
  salesItem!: EntityTable<SalesItemRow, "id">;
  purchaseOrder!: EntityTable<PurchaseOrderRow, "id">;
  purchaseItem!: EntityTable<PurchaseItemRow, "id">;
  stockLedger!: EntityTable<StockLedgerRow, "id">;
  syncQueue!: EntityTable<SyncQueueRow, "id">;
  meta!: EntityTable<MetaRow, "key">;
  suppliers!: EntityTable<NamedRow, "id">;
  customers!: EntityTable<NamedRow, "id">;
  brands!: EntityTable<NamedRow, "id">;
  categories!: EntityTable<NamedRow, "id">;
  syncHistory!: EntityTable<SyncHistoryRow, "id">;

  constructor() {
    super("autostock_mobile");
    this.version(1).stores({
      parts: "id, part_number, oe_number, pinyin, name, category_id, updated_at",
      stockSnapshot: "part_id, quantity, updated_at",
      salesOrder: "id, order_no, order_date, sync_status, updated_at",
      salesItem: "id, order_id, part_id, sync_status",
      purchaseOrder: "id, order_no, order_date, sync_status, updated_at",
      purchaseItem: "id, order_id, part_id, sync_status",
      stockLedger: "id, part_id, source_id, occurred_at, sync_status",
      syncQueue: "id, table_name, row_id, op, created_at",
      meta: "key",
      suppliers: "id, name, updated_at",
      customers: "id, name, updated_at",
      brands: "id, name, updated_at",
      categories: "id, name, updated_at",
    });
    this.version(2).stores({
      parts: "id, part_number, oe_number, pinyin, name, category_id, updated_at, merged_into",
      stockSnapshot: "part_id, quantity, updated_at",
      salesOrder: "id, order_no, order_date, sync_status, updated_at",
      salesItem: "id, order_id, part_id, sync_status",
      purchaseOrder: "id, order_no, order_date, sync_status, updated_at",
      purchaseItem: "id, order_id, part_id, sync_status",
      stockLedger: "id, part_id, source_id, occurred_at, sync_status",
      syncQueue: "id, table_name, row_id, op, created_at",
      meta: "key",
      suppliers: "id, name, updated_at",
      customers: "id, name, updated_at",
      brands: "id, name, updated_at",
      categories: "id, name, updated_at",
      syncHistory: "id, started_at, result",
    });
  }
}

export const db = new AutoStockMobileDB();

export async function getMeta(key: string): Promise<string | null> {
  return (await db.meta.get(key))?.value ?? null;
}

export async function setMeta(key: string, value: string): Promise<void> {
  await db.meta.put({ key, value });
}
